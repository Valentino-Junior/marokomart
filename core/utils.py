import base64

class PayHeroConfig:
    @staticmethod
    def generate_auth_token():
        username = "ZOE6GtrwIi9PeRy5UtjB"  # Replace with your username
        password = "AQjrk2UH0OC4crhB5UfTO3ZMZZ7OTMcBpUGPEZxW"
        credentials = f"{username}:{password}"
        return f"Basic {base64.b64encode(credentials.encode()).decode()}"

    @staticmethod
    def get_callback_url(request):
        return f"{request.scheme}://{request.get_host()}/mpesa/callback/"
