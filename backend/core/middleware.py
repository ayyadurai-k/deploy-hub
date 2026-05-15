import uuid

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get("HTTP_X_REQUEST_ID", "").strip()
        request_id = incoming if incoming else uuid.uuid4().hex
        request.request_id = request_id
        response = self.get_response(request)
        response[REQUEST_ID_HEADER] = request_id
        return response
