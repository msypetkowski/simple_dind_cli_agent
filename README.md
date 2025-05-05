### Simple Docker in Docker CLI Agent

DO NOT USE INSIDE NON-ISOLATED ENVIRONMENT -- `--priviledged` flag is dangerous here.
USE ONLY ON A SAFELY ISOLATED VM -- AGENT HAS HOST'S ROOT PERMISSIONS!

Just spawn an generic agent inside your current dir. Purpose:
- it can e.g. write and test a Dockerfile for you
- it can do various operations in your current directory
- it is WEAKLY isolated -- probabilistically it will only change files in the current directory

### BUILDING

```bash
docker build -t simple_dind_cli:latest .
```

### RUNNING

The following will just run a very simple streamlit app inside your current working directory.
You can copy run.sh from anywhere -- doesn't have to be in this repo.

```bash
export OPENAI_API_KEY=...
run.sh
```
