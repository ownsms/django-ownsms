from importlib.resources import files

from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods


def _schema_text():
    return files("ownsms").joinpath("openapi.yaml").read_text(encoding="utf-8")


@require_http_methods(["GET"])
def openapi_schema(request):
    return HttpResponse(_schema_text(), content_type="application/yaml")


_SWAGGER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>ownsms API</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"/>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.ui = SwaggerUIBundle({{ url: "{schema_url}", dom_id: "#swagger-ui" }});
  </script>
</body>
</html>"""


@require_http_methods(["GET"])
def swagger_ui(request):
    url = reverse("ownsms:openapi")
    return HttpResponse(_SWAGGER_HTML.format(schema_url=url), content_type="text/html")
