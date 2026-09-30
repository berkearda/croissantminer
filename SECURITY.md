# Security

## Reporting a problem

Please do not report security problems in public issues. Use the **Report a vulnerability** button in the
repository's Security tab, or write to bearda@ethz.ch.

## API keys

- The command line and the Python API read keys from the environment or a `.env` file in the folder you run
  from. They never take a key as a command-line argument, so keys do not end up in your shell history.
- Keep `.env` out of version control (it is listed in `.gitignore`).
- The [demo](https://huggingface.co/spaces/bearda/croissantminer) uses the key you enter only for your own run:
  it is passed to the model provider and not stored or logged.
- The paper you process is sent to the model provider you choose, under your key and the provider's terms.
