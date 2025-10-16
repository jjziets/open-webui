from test.util.abstract_integration_test import AbstractPostgresTest
from test.util.mock_user import mock_webui_user

from open_webui.env import WEBUI_LITELLM_DEFAULT_MODEL, WEBUI_LITELLM_DEFAULT_URL


class TestAuths(AbstractPostgresTest):
    BASE_PATH = "/api/v1/auths"

    def setup_class(cls):
        super().setup_class()
        from open_webui.models.auths import Auths
        from open_webui.models.users import Users

        cls.users = Users
        cls.auths = Auths

    def test_get_session_user(self):
        with mock_webui_user():
            response = self.fast_api_client.get(self.create_url(""))
        assert response.status_code == 200
        assert response.json() == {
            "id": "1",
            "name": "John Doe",
            "email": "john.doe@openwebui.com",
            "role": "user",
            "profile_image_url": "/user.png",
        }

    def test_update_profile(self):
        from open_webui.utils.auth import get_password_hash

        user = self.auths.insert_new_auth(
            email="john.doe@openwebui.com",
            password=get_password_hash("old_password"),
            name="John Doe",
            profile_image_url="/user.png",
            role="user",
        )

        with mock_webui_user(id=user.id):
            response = self.fast_api_client.post(
                self.create_url("/update/profile"),
                json={"name": "John Doe 2", "profile_image_url": "/user2.png"},
            )
        assert response.status_code == 200
        db_user = self.users.get_user_by_id(user.id)
        assert db_user.name == "John Doe 2"
        assert db_user.profile_image_url == "/user2.png"

    def test_update_password(self):
        from open_webui.utils.auth import get_password_hash

        user = self.auths.insert_new_auth(
            email="john.doe@openwebui.com",
            password=get_password_hash("old_password"),
            name="John Doe",
            profile_image_url="/user.png",
            role="user",
        )

        with mock_webui_user(id=user.id):
            response = self.fast_api_client.post(
                self.create_url("/update/password"),
                json={"password": "old_password", "new_password": "new_password"},
            )
        assert response.status_code == 200

        old_auth = self.auths.authenticate_user(
            "john.doe@openwebui.com", "old_password"
        )
        assert old_auth is None
        new_auth = self.auths.authenticate_user(
            "john.doe@openwebui.com", "new_password"
        )
        assert new_auth is not None

    def test_signin(self):
        from open_webui.utils.auth import get_password_hash

        user = self.auths.insert_new_auth(
            email="john.doe@openwebui.com",
            password=get_password_hash("password"),
            name="John Doe",
            profile_image_url="/user.png",
            role="user",
        )
        response = self.fast_api_client.post(
            self.create_url("/signin"),
            json={"email": "john.doe@openwebui.com", "password": "password"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user.id
        assert data["name"] == "John Doe"
        assert data["email"] == "john.doe@openwebui.com"
        assert data["role"] == "user"
        assert data["profile_image_url"] == "/user.png"
        assert data["token"] is not None and len(data["token"]) > 0
        assert data["token_type"] == "Bearer"

    def test_signup(self):
        response = self.fast_api_client.post(
            self.create_url("/signup"),
            json={
                "name": "John Doe",
                "email": "john.doe@openwebui.com",
                "password": "password",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None and len(data["id"]) > 0
        assert data["name"] == "John Doe"
        assert data["email"] == "john.doe@openwebui.com"
        assert data["role"] in ["admin", "user", "pending"]
        assert data["profile_image_url"] == "/user.png"
        assert data["token"] is not None and len(data["token"]) > 0
        assert data["token_type"] == "Bearer"

    def test_add_user(self):
        with mock_webui_user():
            response = self.fast_api_client.post(
                self.create_url("/add"),
                json={
                    "name": "John Doe 2",
                    "email": "john.doe2@openwebui.com",
                    "password": "password2",
                    "role": "admin",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None and len(data["id"]) > 0
        assert data["name"] == "John Doe 2"
        assert data["email"] == "john.doe2@openwebui.com"
        assert data["role"] == "admin"
        assert data["profile_image_url"] == "/user.png"
        assert data["token"] is not None and len(data["token"]) > 0
        assert data["token_type"] == "Bearer"

    def test_get_admin_details(self):
        self.auths.insert_new_auth(
            email="john.doe@openwebui.com",
            password="password",
            name="John Doe",
            profile_image_url="/user.png",
            role="admin",
        )
        with mock_webui_user():
            response = self.fast_api_client.get(self.create_url("/admin/details"))

        assert response.status_code == 200
        assert response.json() == {
            "name": "John Doe",
            "email": "john.doe@openwebui.com",
        }

    def test_create_api_key_(self):
        user = self.auths.insert_new_auth(
            email="john.doe@openwebui.com",
            password="password",
            name="John Doe",
            profile_image_url="/user.png",
            role="admin",
        )
        with mock_webui_user(id=user.id):
            response = self.fast_api_client.post(self.create_url("/api_key"))
        assert response.status_code == 200
        data = response.json()
        assert data["api_key"] is not None
        assert len(data["api_key"]) > 0

    def test_delete_api_key(self):
        user = self.auths.insert_new_auth(
            email="john.doe@openwebui.com",
            password="password",
            name="John Doe",
            profile_image_url="/user.png",
            role="admin",
        )
        self.users.update_user_api_key_by_id(user.id, "abc")
        with mock_webui_user(id=user.id):
            response = self.fast_api_client.delete(self.create_url("/api_key"))
        assert response.status_code == 200
        assert response.json() == True
        db_user = self.users.get_user_by_id(user.id)
        assert db_user.api_key is None

    def test_get_api_key(self):
        user = self.auths.insert_new_auth(
            email="john.doe@openwebui.com",
            password="password",
            name="John Doe",
            profile_image_url="/user.png",
            role="admin",
        )
        self.users.update_user_api_key_by_id(user.id, "abc")
        with mock_webui_user(id=user.id):
            response = self.fast_api_client.get(self.create_url("/api_key"))
        assert response.status_code == 200
        assert response.json() == {"api_key": "abc"}

    def test_trusted_header_login_without_api_key(self):
        response = self.fast_api_client.post(
            self.create_url("/signin"),
            json={"email": "unused@openwebui.com", "password": "unused"},
            headers={"X-Webui-Email": "trusted@example.com"},
        )

        assert response.status_code == 200

        user = self.users.get_user_by_email("trusted@example.com")
        assert user is not None

        settings = user.settings.model_dump() if user.settings else {}
        ui_settings = settings.get("ui") or {}
        assert "directConnections" not in ui_settings

    def test_trusted_header_creates_direct_connection(self):
        api_key = "key-123"
        base_url = "https://litellm.example/v1/"

        response = self.fast_api_client.post(
            self.create_url("/signin"),
            json={"email": "ignored@openwebui.com", "password": "ignored"},
            headers={
                "X-Webui-Email": "trusted@example.com",
                "X-Webui-Name": "Trusted User",
                "X-User-Api-Key": api_key,
                "X-User-Litellm-Url": base_url,
            },
        )

        assert response.status_code == 200

        user = self.users.get_user_by_email("trusted@example.com")
        assert user is not None

        settings = user.settings.model_dump()
        ui_settings = settings.get("ui") or {}
        direct_connections = ui_settings.get("directConnections")

        assert direct_connections is not None
        assert direct_connections["OPENAI_API_KEYS"][0] == api_key
        assert direct_connections["OPENAI_API_BASE_URLS"][0] == base_url.rstrip("/")
        assert (
            direct_connections["OPENAI_API_CONFIGS"]["0"].get("slug")
            == "cryptolabs-litellm"
        )

        models = ui_settings.get("models") or []
        assert models
        assert models[0] == WEBUI_LITELLM_DEFAULT_MODEL

    def test_trusted_header_updates_existing_connection(self):
        email = "trusted@example.com"
        initial_key = "initial-key"
        new_key = "rotated-key"

        first_response = self.fast_api_client.post(
            self.create_url("/signin"),
            json={"email": "ignored@openwebui.com", "password": "ignored"},
            headers={
                "X-Webui-Email": email,
                "X-User-Api-Key": initial_key,
                "X-User-Litellm-Url": WEBUI_LITELLM_DEFAULT_URL,
            },
        )
        assert first_response.status_code == 200

        second_response = self.fast_api_client.post(
            self.create_url("/signin"),
            json={"email": "ignored@openwebui.com", "password": "ignored"},
            headers={
                "X-Webui-Email": email,
                "X-User-Api-Key": new_key,
                "X-User-Litellm-Url": WEBUI_LITELLM_DEFAULT_URL,
            },
        )
        assert second_response.status_code == 200

        user = self.users.get_user_by_email(email)
        assert user is not None

        settings = user.settings.model_dump()
        ui_settings = settings.get("ui") or {}
        direct_connections = ui_settings.get("directConnections") or {}

        assert direct_connections["OPENAI_API_KEYS"] == [new_key]
        assert direct_connections["OPENAI_API_BASE_URLS"] == [
            WEBUI_LITELLM_DEFAULT_URL.rstrip("/")
        ]

        models = ui_settings.get("models") or []
        assert models
        assert models.count(WEBUI_LITELLM_DEFAULT_MODEL) == 1
