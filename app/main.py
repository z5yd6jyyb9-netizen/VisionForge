import base64
import io
import os
import threading
import time
from typing import Optional

import cv2
import numpy as np
import psutil
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field

MODEL_ID = os.getenv('MODEL_ID', 'stabilityai/sd-turbo')
CLIP_ID = os.getenv('CLIP_ID', 'openai/clip-vit-base-patch32')
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
DTYPE = torch.float16 if DEVICE == 'cuda' else torch.float32
RESOLUTIONS = (256, 384, 512)

app = FastAPI(title='VisionForge AI', version='1.1.0')
app.mount('/static', StaticFiles(directory='app/static'), name='static')
_pipe = None
_clip_model = None
_clip_processor = None
_load_lock = threading.Lock()
_inference_lock = threading.Lock()


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=500)
    mode: str = Field(default='balanced', pattern='^(fast|balanced|quality|auto)$')
    classical_enhance: bool = True
    seed: Optional[int] = None
    resolution: int = Field(default=512, json_schema_extra={'enum': [256, 384, 512]})


def load_generator():
    global _pipe
    if _pipe is None:
        with _load_lock:
            if _pipe is None:
                from diffusers import AutoPipelineForText2Image
                kwargs = {'torch_dtype': DTYPE}
                if DEVICE == 'cuda':
                    kwargs['variant'] = 'fp16'
                _pipe = AutoPipelineForText2Image.from_pretrained(MODEL_ID, **kwargs).to(DEVICE)
                if DEVICE == 'cuda':
                    try:
                        _pipe.enable_attention_slicing()
                    except Exception:
                        pass
    return _pipe


def load_clip():
    global _clip_model, _clip_processor
    if _clip_model is None:
        with _load_lock:
            if _clip_model is None:
                from transformers import CLIPModel, CLIPProcessor
                _clip_processor = CLIPProcessor.from_pretrained(CLIP_ID)
                _clip_model = CLIPModel.from_pretrained(CLIP_ID).to(DEVICE)
                _clip_model.eval()
    return _clip_model, _clip_processor


def classical_postprocess(image: Image.Image) -> Image.Image:
    """CLAHE on luminance, edge-aware denoising and restrained sharpening."""
    rgb = np.array(image.convert('RGB'))
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    l2 = cv2.createCLAHE(clipLimit=1.35, tileGridSize=(8, 8)).apply(l)
    out = cv2.cvtColor(cv2.merge((l2, a, b)), cv2.COLOR_LAB2RGB)
    out = cv2.bilateralFilter(out, d=5, sigmaColor=20, sigmaSpace=20)
    blur = cv2.GaussianBlur(out, (0, 0), 1.0)
    sharp = cv2.addWeighted(out, 1.12, blur, -0.12, 0)
    return Image.fromarray(np.clip(sharp, 0, 255).astype(np.uint8))


def clip_score(prompt: str, image: Image.Image) -> Optional[float]:
    try:
        model, processor = load_clip()
        inputs = processor(text=[prompt], images=image, return_tensors='pt', padding=True).to(DEVICE)
        with torch.no_grad():
            outputs = model(**inputs)
            score = torch.nn.functional.cosine_similarity(outputs.image_embeds, outputs.text_embeds).item()
        return round(float(score), 4)
    except Exception as exc:
        print('CLIP evaluation unavailable:', repr(exc))
        return None


def resource_snapshot():
    vm = psutil.virtual_memory()
    result = {
        'device': DEVICE,
        'system_ram_available_mb': round(vm.available / (1024 ** 2), 1),
        'process_rss_mb': round(psutil.Process().memory_info().rss / (1024 ** 2), 1),
        'gpu_free_mb': None,
    }
    if DEVICE == 'cuda':
        free_bytes, _ = torch.cuda.mem_get_info()
        result['gpu_free_mb'] = round(free_bytes / (1024 ** 2), 1)
    return result


def choose_auto_profile(requested_resolution: int):
    snapshot = resource_snapshot()
    if DEVICE == 'cuda':
        free_mb = snapshot['gpu_free_mb'] or 0
        if free_mb >= 8192:
            mode, resolution, reason = 'quality', requested_resolution, 'GPU has at least 8 GB free.'
        elif free_mb >= 4096:
            mode, resolution, reason = 'balanced', min(requested_resolution, 384), 'GPU has 4–8 GB free; resolution capped at 384.'
        else:
            mode, resolution, reason = 'fast', min(requested_resolution, 256), 'GPU has under 4 GB free; using the smallest output and fewest steps.'
    else:
        available_mb = snapshot['system_ram_available_mb']
        if available_mb >= 8192:
            mode, resolution, reason = 'balanced', min(requested_resolution, 384), 'CPU-only device; using 2 steps and capping resolution at 384.'
        else:
            mode, resolution, reason = 'fast', min(requested_resolution, 256), 'CPU-only device with under 8 GB available RAM; using the smallest output and fewest steps.'
    return mode, resolution, reason, snapshot


def run_generation(req: GenerateRequest, forced_mode: Optional[str] = None):
    mode = forced_mode or req.mode
    resolution = req.resolution
    auto_reason = None
    # Load the diffusion weights before Auto samples free memory; otherwise the
    # first request would make its decision before accounting for the model.
    pipe = load_generator()
    resource_before = resource_snapshot()
    if mode == 'auto':
        mode, resolution, auto_reason, resource_before = choose_auto_profile(req.resolution)
    steps = {'fast': 1, 'balanced': 2, 'quality': 4}[mode]
    generator = torch.Generator(device=DEVICE).manual_seed(int(req.seed)) if req.seed is not None else None
    if DEVICE == 'cuda':
        torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    with torch.inference_mode():
        result = pipe(prompt=req.prompt, num_inference_steps=steps, guidance_scale=0.0,
                      generator=generator, height=resolution, width=resolution)
    raw = result.images[0]
    generation_ms = round((time.perf_counter() - start) * 1000, 1)
    # Capture generator memory before loading/running CLIP, so the reading describes generation.
    peak_gpu_mb = round(torch.cuda.max_memory_allocated() / (1024 ** 2), 1) if DEVICE == 'cuda' else None
    final = classical_postprocess(raw) if req.classical_enhance else raw
    eval_start = time.perf_counter()
    score = clip_score(req.prompt, final)
    eval_ms = round((time.perf_counter() - eval_start) * 1000, 1)
    buf = io.BytesIO()
    final.save(buf, format='PNG')
    after = resource_snapshot()
    encoded = base64.b64encode(buf.getvalue()).decode('ascii')
    return {
        'image': encoded, 'mime_type': 'image/png', 'mode': mode, 'requested_mode': req.mode,
        'steps': steps, 'resolution': resolution, 'generation_ms': generation_ms,
        'clip_score': score, 'clip_eval_ms': eval_ms, 'peak_gpu_memory_mb': peak_gpu_mb,
        'process_rss_before_mb': resource_before['process_rss_mb'],
        'process_rss_after_mb': after['process_rss_mb'],
        'system_ram_available_before_mb': resource_before['system_ram_available_mb'],
        'system_ram_available_after_mb': after['system_ram_available_mb'],
        'gpu_free_before_mb': resource_before['gpu_free_mb'],
        'device': DEVICE, 'model': MODEL_ID, 'dtype': str(DTYPE).replace('torch.', ''),
        'classical_postprocess': req.classical_enhance, 'auto_reason': auto_reason,
        'note': 'Generation latency excludes initial model loading. CPU RAM values are process/system snapshots, not peak RSS.',
    }


@app.get('/')
def home():
    return FileResponse('app/static/index.html')


@app.get('/health')
def health():
    return {'status': 'ok', 'model': MODEL_ID, **resource_snapshot()}


@app.post('/generate')
def generate(req: GenerateRequest):
    if req.resolution not in RESOLUTIONS:
        raise HTTPException(status_code=422, detail=f'Resolution must be one of {RESOLUTIONS}.')
    try:
        # Serialize access to the shared diffusion pipeline and its peak-memory counter.
        with _inference_lock:
            return run_generation(req)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Generation failed: {str(exc)[:400]}')


@app.post('/compare')
def compare(req: GenerateRequest):
    if req.resolution not in RESOLUTIONS:
        raise HTTPException(status_code=422, detail=f'Resolution must be one of {RESOLUTIONS}.')
    # Same prompt, seed and requested resolution across all three conditions.
    conditions = [('Baseline · 4 steps', 'quality'), ('Optimized · 1 step', 'fast'), ('Adaptive · Auto', 'auto')]
    results = []
    try:
        with _inference_lock:
            for label, mode in conditions:
                result = run_generation(req, forced_mode=mode)
                result['label'] = label
                results.append(result)
        return {'prompt': req.prompt, 'seed': req.seed, 'requested_resolution': req.resolution,
                'same_prompt_and_seed': True, 'results': results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Comparison failed: {str(exc)[:400]}')
