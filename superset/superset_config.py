FEATURE_FLAGS = {
    "EMBEDDED_SUPERSET": True,
}
ENABLE_CORS = True
CORS_OPTIONS = {
    'supports_credentials': True,
    'allow_headers': ['*'],
    'resources': ['*'],
    'origins': ['http://localhost:3000']
}
