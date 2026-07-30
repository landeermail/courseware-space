from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class TimelinePrimitiveTests(unittest.TestCase):
    def test_creation_emits_paused_zero_state_and_browser_markers(self) -> None:
        primitive = (ROOT / "harness" / "primitives.js").read_text(encoding="utf-8")
        script = """
globalThis.document={documentElement:{attrs:{},setAttribute(key,value){this.attrs[key]=value;}}};
globalThis.requestAnimationFrame=()=>1;
globalThis.cancelAnimationFrame=()=>{};
const states=[];
CoursewarePrimitives.createTimeline({durationPhysicalS:2,onChange(state){states.push(state);}});
console.log(JSON.stringify({states,attrs:document.documentElement.attrs}));
"""
        result = subprocess.run(
            ["node", "-e", primitive + script],
            text=True,
            capture_output=True,
            check=True,
            timeout=5,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["states"], [{"physicalTimeS": 0, "demoRate": 0.5, "playing": False}])
        self.assertEqual(payload["attrs"]["data-harness-physical-time"], "0.000000")
        self.assertEqual(payload["attrs"]["data-harness-playing"], "false")


if __name__ == "__main__":
    unittest.main()
