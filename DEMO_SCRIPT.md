# 3-minute demo script — VisionForge / T83

**0:00–0:25 — Problem**  
“Our challenge is P3: text-to-image generation under mobile-style compute constraints. High-quality diffusion generation can be expensive in time and memory. We built VisionForge to expose and measure the quality–compute trade-off.”

**0:25–0:55 — Architecture**  
“The user prompt reaches our FastAPI backend. Diffusers runs pretrained SD-Turbo. We offer 1, 2 and 4 denoising-step budgets plus Auto, which chooses a step budget and caps resolution based on current free GPU memory or available system RAM. The generated image can pass through an OpenCV stage: CLAHE on luminance, bilateral filtering and mild sharpening. CLIP then estimates prompt-image alignment.”

**0:55–1:45 — Live demo**  
“Enter one prompt and fixed seed, then select Compare. VisionForge runs a 4-step reference, a 1-step lower-compute run, and Auto sequentially with the same prompt and seed. Compare the three images and measured generation time, CLIP cosine, output size, CUDA generation peak and CPU process RAM snapshot. The initial model load happens before generation timing; it is excluded from the generation timer. Auto reports why it chose its profile.”

**1:45–2:20 — Evaluation**  
“The evaluation script measures Fast, Balanced, Quality and Auto across a fixed prompt set, with classical post-processing both on and off. It records raw runs, selected Auto settings, latency, CLIP cosine, CUDA peak and CPU process RAM. CLIP cosine is a relative alignment indicator, not a probability. We report measured medians from the hardware used for the run.”

**2:20–3:00 — Limitations and close**  
“Our prototype demonstrates resource-aware inference on a server. It is not yet a native on-device mobile deployment, and cloud GPU memory is not mobile RAM. Auto is a transparent resource heuristic, not proof of mobile performance. Lower step counts can trade detail or prompt alignment for speed. Our next step is device-side quantization and benchmarking on a real mobile target.”

## Likely viva questions
- **Why SD-Turbo?** It is a distilled text-to-image model designed for very few inference steps, making it suitable for testing low-step inference budgets.
- **What is optimized?** The inference budget (step count), FP16 on CUDA, and attention slicing where supported. We did not fine-tune weights.
- **What does CLIP score mean?** Cosine similarity between text and image embeddings; useful for relative comparisons, not a calibrated probability or full image-quality metric.
- **Why CLAHE?** It improves local luminance contrast; bilateral filtering smooths while preserving edges; mild sharpening restores perceived crispness. It can also introduce artifacts, so we ablate it.
- **Is it running on a phone?** No. The current deployment is a GPU-backed prototype that explores mobile-relevant efficiency. Native mobile deployment remains future work.
- **Why no PSNR/SSIM?** There is no paired ground-truth image for each arbitrary prompt. Those metrics would be invalid without references.
