import importlib.util
import sys
import unittest
from pathlib import Path


RELEASE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RELEASE_ROOT))
SPEC = importlib.util.spec_from_file_location("whiteboard_release_server", RELEASE_ROOT / "webapp" / "server.py")
assert SPEC and SPEC.loader
SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVER)


class IndexTTSGradioCompatTests(unittest.TestCase):
    def test_param_names_prefer_parameter_name(self) -> None:
        names = SERVER._gradio_endpoint_param_names(
            [
                {"parameter_name": "lang_choice", "label": "语言"},
                {"label": "duration_factor"},
            ]
        )
        self.assertEqual(names, {"lang_choice", "duration_factor"})

    def test_pick_emo_prefers_v25_label_when_present(self) -> None:
        parameters = [
            {
                "parameter_name": "emo_control_method",
                "parameter_default": "与音色参考音频相同",
                "type": {
                    "enum": ["与音色参考音频相同", "使用情感参考音频", "使用情感向量控制"],
                },
            }
        ]
        self.assertEqual(SERVER._pick_emo_same_as_voice(parameters), "与音色参考音频相同")

    def test_pick_emo_falls_back_to_legacy_label(self) -> None:
        parameters = [
            {
                "parameter_name": "emo_control_method",
                "parameter_default": "与参考音频的音色相同",
                "type": {
                    "enum": ["与参考音频的音色相同", "使用情感参考音频", "使用情感向量控制"],
                },
            }
        ]
        self.assertEqual(SERVER._pick_emo_same_as_voice(parameters), "与参考音频的音色相同")

    def test_pick_emo_matches_spaced_choices(self) -> None:
        parameters = [
            {
                "parameter_name": "emo_control_method",
                "type": {"enum": [" 与音色参考音频相同 ", " 使用情感参考音频 "]},
            }
        ]
        self.assertEqual(SERVER._pick_emo_same_as_voice(parameters), " 与音色参考音频相同 ")

    def test_v25_feature_flag_from_param_names(self) -> None:
        legacy = SERVER._gradio_endpoint_param_names(
            [{"parameter_name": "emo_control_method"}, {"parameter_name": "prompt"}]
        )
        modern = legacy | {"lang_choice", "duration_factor"}
        self.assertFalse("lang_choice" in legacy or "duration_factor" in legacy)
        self.assertTrue("lang_choice" in modern or "duration_factor" in modern)
        self.assertEqual(SERVER._EMO_SAME_AS_VOICE_CANDIDATES[1], "与参考音频的音色相同")


if __name__ == "__main__":
    unittest.main()
