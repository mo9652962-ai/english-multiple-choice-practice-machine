from pathlib import Path


WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "android.yml"


def test_android_tag_workflow_uses_signed_release_apk_for_manifest_and_checks() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "app-release.apk" in source
    assert 'apk=frontend/android/app/build/outputs/apk/release/app-release.apk' in source
    assert '--artifact "$apk"' in source
    assert 'apks+=("frontend/android/app/build/outputs/apk/release/app-release.apk")' in source


def test_android_workflow_keeps_debug_artifact_for_non_tag_runs() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert 'apks=("frontend/android/app/build/outputs/apk/debug/app-debug.apk")' in source
    assert 'frontend/android/app/build/outputs/apk/debug/app-debug.apk' in source
    assert "if: ${{ !startsWith(github.ref, 'refs/tags/v') }}" in source
    assert "name: epm-android-debug-${{ github.sha }}" in source


def test_android_tag_upload_contains_release_apk_and_manifest() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "if: ${{ startsWith(github.ref, 'refs/tags/v') }}" in source
    assert "name: epm-android-release-${{ github.sha }}" in source
    assert "frontend/android/app/build/outputs/apk/release/app-release.apk" in source
    assert "android-release-manifest.json" in source
