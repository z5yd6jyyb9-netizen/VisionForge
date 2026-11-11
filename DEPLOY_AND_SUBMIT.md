# Team T83 — GitHub and Hugging Face release checklist

## Current repository state

- Submission repository: https://github.com/jprasidhbtech24-dot/VisionForge
- Development branch: `feat/adaptive-resource-comparison`, tracking `fork/feat/adaptive-resource-comparison`.
- The final reviewed feature branch and personal `main` were pushed to the selected repository at the same release commit using a fast-forward. Verify the current commit hash with Git before submitting.
- The initial source snapshot inspected for this work was commit `822e131`; the root `.gitignore` was present locally and has been included with its required rules preserved.
- Never commit access tokens, private keys, `.env` files or local model weights.

## Before publishing

1. Create/activate a clean Python environment and install `requirements.txt`.
2. Run `python -m compileall -q app evaluate.py`.
3. Start the app on port 7860; check `/health` and generate an image in the browser.
4. Run the evaluation script only on a working inference server. Three repeats over five prompts, four profiles and two post-processing settings plus warmups means 160 generation requests.
5. Save raw measurements with hardware, date, software versions, model revision, prompt/seed and commit recorded. Inspect outputs before reporting.
6. Review changes and secret scans before each commit and push.

## GitHub release

For any future changes, push the reviewed feature branch to the selected personal repository:

```powershell
git push fork feat/adaptive-resource-comparison
```

After review and successful verification, advance submission `main` without rewriting history:

```powershell
git switch main
git merge --ff-only feat/adaptive-resource-comparison
git push fork main
```

If the remote main branch has moved, stop and inspect the new commits before merging. Do not force-push.

## Hugging Face Spaces

The root `README.md` contains the Space YAML metadata: `sdk: docker` and `app_port: 7860`. The separate `README_HF.md` is supplemental; Spaces reads the root README.

1. Create a **Public Docker Space** under the intended account if account eligibility permits.
2. Link/synchronize the selected GitHub repository through an authenticated deployment workflow, or push the reviewed branch to the Space Git remote using the Hugging Face credential helper.
3. If using GitHub Actions, store the Hugging Face write token as a repository secret. Never put it in source files or remote URLs.
4. Run Docker on CPU only if it is practical for the live demo. Hugging Face currently lists CPU Basic with no hourly hardware charge, but Docker Space creation requires a paid plan unless an eligible free exception applies. GPU hardware is paid; do not select or purchase it without approval. CPU inference may be extremely slow.
5. Wait for the build, check `/health`, then complete an actual image generation. Report the URL only after both the public app and generation work.

Space git example (replace the owner only after confirming the account name; keep credentials out of the URL):

```bash
git remote add hf https://huggingface.co/spaces/<confirmed-owner>/visionforge-t83
git push hf feat/adaptive-resource-comparison:main
```

## Release evidence

Record the public GitHub URL, exact commit hash, public Space URL (if deployed), selected hardware, model ID, date, raw evaluation CSV and screenshots. Distinguish a static showcase from live inference. Do not claim deployment succeeded until the public URL has been opened and an end-to-end generation completed.
