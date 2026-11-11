# Hugging Face Space notes

Hugging Face Spaces reads its Docker configuration from the YAML block at the top of the repository's root `README.md`. That file declares `sdk: docker` and `app_port: 7860`; this supplemental note is not a replacement Space configuration.

The application downloads SD-Turbo and CLIP weights on first use. CPU inference may be extremely slow. See the root README and `DEPLOY_AND_SUBMIT.md` for setup, evaluation, hardware costs, and deployment verification steps. Do not report a live Space until the public app has completed an image generation.
