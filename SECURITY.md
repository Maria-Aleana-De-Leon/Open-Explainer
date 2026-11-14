# Security policy

## Supported versions

Open Explainer is in public beta. Security fixes are made on the latest version on `main`.

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Report them privately through GitHub:
**Security** tab of this repository → **Report a vulnerability**. Include the affected version or commit, steps to
reproduce, and the impact you expect.

We aim to acknowledge reports within a week and will tell you when a fix is published.

## Scope and design notes

- Open Explainer runs locally. It calls FFmpeg and, optionally, a text-to-speech provider you choose.
- API keys (for example `ELEVENLABS_API_KEY`) are read from the environment only and are never written to project
  files or logs. Please report any case where a key is printed or stored.
- `oex tts --provider command` runs the command you give it on your machine. Only use commands you trust.
- Projects, recordings, mascot images and renders stay on your machine; nothing is uploaded by `oex`.
