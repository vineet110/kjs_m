"""Background jobs (runner.py). Each service registers its own jobs with @job when it is imported;
main.py imports those services. Nothing is imported here on purpose: the services import
app.jobs.runner, so importing them from this file made a loop (python -m app.seed crashed with
"partially initialized module 'app.services.file_service'")."""
