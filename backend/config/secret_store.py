import subprocess
import platform

from config.store import config_store


class SecretStore:
    def __init__(self):
        self._system = platform.system()
        self._service_names = ["Sigorjob", "AgentPlatform"]
        self._fallback_prefix = "__secret__:"

    def get(self, key: str) -> str | None:
        if self._system == "Darwin":
            value = self._get_macos_keychain(key)
            if value is not None:
                return value
        value = config_store.get(self._fallback_key(key))
        if isinstance(value, str) and value.strip():
            return value
        return None

    def set(self, key: str, value: str) -> tuple[bool, str | None]:
        if self._system == "Darwin":
            ok, error = self._set_macos_keychain(key, value)
            if ok:
                config_store.delete(self._fallback_key(key))
                return True, None
            return False, error

        config_store.set(self._fallback_key(key), value)
        return True, None

    def delete(self, key: str) -> tuple[bool, str | None]:
        errors: list[str] = []
        if self._system == "Darwin":
            ok, error = self._delete_macos_keychain(key)
            if not ok and error:
                errors.append(error)
        config_store.delete(self._fallback_key(key))
        return (not errors), ("; ".join(errors) if errors else None)

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    def backend(self, key: str) -> str:
        if self._system == "Darwin":
            return "keychain"
        return "config"

    def _fallback_key(self, key: str) -> str:
        return f"{self._fallback_prefix}{key}"

    def _get_macos_keychain(self, key: str) -> str | None:
        for service_name in self._service_names:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", service_name, "-a", key, "-w"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                value = result.stdout.strip()
                if value:
                    return value
        return None

    def _set_macos_keychain(self, key: str, value: str) -> tuple[bool, str | None]:
        result = subprocess.run(
            ["security", "add-generic-password", "-U", "-s", self._service_names[0], "-a", key, "-w", value],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return False, (result.stderr.strip() or "failed to save secret to Keychain")
        return True, None

    def _delete_macos_keychain(self, key: str) -> tuple[bool, str | None]:
        errors: list[str] = []
        for service_name in self._service_names:
            result = subprocess.run(
                ["security", "delete-generic-password", "-s", service_name, "-a", key],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                continue
            stderr = (result.stderr or "").strip()
            if "could not be found" in stderr.lower():
                continue
            errors.append(stderr or f"failed to delete secret from Keychain ({service_name})")
        if errors:
            return False, "; ".join(errors)
        return True, None


secret_store = SecretStore()
