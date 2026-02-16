"""
Grounding tests for contraband_js.sh - verifies JS contraband patterns are actually caught.

Created based on grounding agent mission (2026-01-30): verify every guardrail pattern works.
"""
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPT = REPO_ROOT / "tools" / "checks" / "contraband_js.sh"


def run_contraband_on_js(code: str) -> subprocess.CompletedProcess:
    """Write JS code to temp file and run contraband_js.sh on it."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
        f.write(code)
        f.flush()
        filepath = f.name

    try:
        return subprocess.run(
            ["bash", str(SCRIPT), filepath],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    finally:
        Path(filepath).unlink()


class TestContrabandjsDetectsEval:
    """Verify contraband_js.sh catches eval patterns."""

    def test_detects_direct_eval(self):
        """contraband_js.sh must fail when eval( found."""
        code = 'const result = eval("1 + 1");'
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on eval("

    def test_detects_eval_in_function(self):
        """contraband_js.sh must fail when eval in function body."""
        code = "function dangerous() { return eval(code); }"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on eval in function"


class TestContrabandjsDetectsFunction:
    """Verify contraband_js.sh catches Function constructor."""

    def test_detects_new_function(self):
        """contraband_js.sh must fail when new Function( found."""
        code = 'const fn = new Function("return 1");'
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on new Function("

    def test_detects_function_call(self):
        """contraband_js.sh must fail when Function( called directly."""
        code = 'const fn = Function("return 1");'
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on Function("


class TestContrabandjsDetectsAsync:
    """Verify contraband_js.sh catches async patterns."""

    def test_detects_settimeout(self):
        """contraband_js.sh must fail when setTimeout found."""
        code = "setTimeout(() => {}, 1000);"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on setTimeout"

    def test_detects_setinterval(self):
        """contraband_js.sh must fail when setInterval found."""
        code = "setInterval(() => {}, 1000);"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on setInterval"


class TestContrabandjsDetectsNondeterminism:
    """Verify contraband_js.sh catches non-determinism."""

    def test_detects_math_random(self):
        """contraband_js.sh must fail when Math.random found."""
        code = "const x = Math.random();"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on Math.random"

    def test_detects_date_now(self):
        """contraband_js.sh must fail when Date.now found."""
        code = "const t = Date.now();"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on Date.now"

    def test_detects_new_date(self):
        """contraband_js.sh must fail when new Date( found."""
        code = "const d = new Date();"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on new Date("


class TestContrabandjsDetectsEnvLeakage:
    """Verify contraband_js.sh catches environment leakage."""

    def test_detects_process_env(self):
        """contraband_js.sh must fail when process.env found."""
        code = "const secret = process.env.SECRET;"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on process.env"


class TestContrabandjsDetectsSubprocess:
    """Verify contraband_js.sh catches subprocess spawning."""

    def test_detects_child_process(self):
        """contraband_js.sh must fail when child_process found."""
        code = "const cp = require('child_process');"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on child_process"

    def test_detects_exec(self):
        """contraband_js.sh must fail when exec( found."""
        code = "exec('ls -la');"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on exec("

    def test_detects_spawn(self):
        """contraband_js.sh must fail when spawn( found."""
        code = "spawn('node', ['script.js']);"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on spawn("


class TestContrabandjsDetectsFileMutation:
    """Verify contraband_js.sh catches file mutation."""

    def test_detects_fs_write(self):
        """contraband_js.sh must fail when fs.write found."""
        code = "fs.writeFileSync('file.txt', 'data');"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on fs.write"

    def test_detects_fs_unlink(self):
        """contraband_js.sh must fail when fs.unlink found."""
        code = "fs.unlinkSync('file.txt');"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on fs.unlink"

    def test_detects_fs_mkdir(self):
        """contraband_js.sh must fail when fs.mkdir found."""
        code = "fs.mkdirSync('newdir');"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on fs.mkdir"


class TestContrabandjsDetectsNetwork:
    """Verify contraband_js.sh catches network access."""

    def test_detects_require_http(self):
        """contraband_js.sh must fail when require http found."""
        code = "const http = require('http');"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on require http"

    def test_detects_fetch(self):
        """contraband_js.sh must fail when fetch( found."""
        code = "fetch('https://example.com');"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on fetch("


class TestContrabandjsDetectsVm:
    """Verify contraband_js.sh catches vm module (eval equivalent)."""

    def test_detects_require_vm(self):
        """contraband_js.sh must fail when require('vm') found."""
        code = "const vm = require('vm');"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on require('vm')"


class TestContrabandjsDetectsCryptoRandom:
    """Verify contraband_js.sh catches crypto randomness."""

    def test_detects_crypto_random(self):
        """contraband_js.sh must fail when crypto.randomBytes found."""
        code = "const bytes = crypto.randomBytes(16);"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on crypto.randomBytes"

    def test_detects_webcrypto(self):
        """contraband_js.sh must fail when webcrypto found."""
        code = "const wc = crypto.webcrypto;"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on webcrypto"

    def test_detects_get_random_values(self):
        """contraband_js.sh must fail when getRandomValues found."""
        code = "crypto.webcrypto.getRandomValues(new Uint8Array(16));"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on getRandomValues"

    def test_detects_crypto_subtle(self):
        """contraband_js.sh must fail when crypto.subtle found."""
        code = "crypto.subtle.generateKey(algo, true, ['sign']);"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on crypto.subtle"

    def test_detects_crypto_generate_key(self):
        """contraband_js.sh must fail when crypto.generateKey found."""
        code = "crypto.generateKey('aes', { length: 256 }, callback);"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on crypto.generateKey"


class TestContrabandjsDetectsWebAssembly:
    """Verify contraband_js.sh catches WebAssembly (arbitrary code execution)."""

    def test_detects_webassembly(self):
        """contraband_js.sh must fail when WebAssembly found."""
        code = "const module = new WebAssembly.Module(buffer);"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on WebAssembly"

    def test_detects_webassembly_instantiate(self):
        """contraband_js.sh must fail when WebAssembly.instantiate found."""
        code = "WebAssembly.instantiate(buffer).then(m => m);"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on WebAssembly.instantiate"


class TestContrabandjsDetectsWorker:
    """Verify contraband_js.sh catches Worker threads."""

    def test_detects_new_worker(self):
        """contraband_js.sh must fail when new Worker found."""
        code = "const worker = new Worker('worker.js');"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on new Worker"

    def test_detects_worker_threads(self):
        """contraband_js.sh must fail when worker_threads found."""
        code = "const { Worker } = require('worker_threads');"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on worker_threads"


class TestContrabandjsDetectsSharedMemory:
    """Verify contraband_js.sh catches shared memory primitives."""

    def test_detects_shared_array_buffer(self):
        """contraband_js.sh must fail when SharedArrayBuffer found."""
        code = "const sab = new SharedArrayBuffer(1024);"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on SharedArrayBuffer"

    def test_detects_atomics(self):
        """contraband_js.sh must fail when Atomics. found."""
        code = "Atomics.add(view, 0, 1);"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on Atomics."


class TestContrabandjsDetectsPromise:
    """Verify contraband_js.sh catches Promise (async without async keyword)."""

    def test_detects_new_promise(self):
        """contraband_js.sh must fail when new Promise found."""
        code = "const p = new Promise((resolve) => resolve(1));"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on new Promise"

    def test_detects_promise_api(self):
        """contraband_js.sh must fail when Promise. API found."""
        code = "Promise.resolve(1).then(x => x);"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on Promise."


class TestContrabandjsDetectsFsMutationVariants:
    """Verify contraband_js.sh catches all fs mutation variants."""

    def test_detects_fs_append(self):
        """contraband_js.sh must fail when fs.append found."""
        code = "fs.appendFileSync('file.txt', 'data');"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on fs.append"

    def test_detects_fs_rm(self):
        """contraband_js.sh must fail when fs.rm found."""
        code = "fs.rmSync('dir', { recursive: true });"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on fs.rm"

    def test_detects_fs_rename(self):
        """contraband_js.sh must fail when fs.rename found."""
        code = "fs.renameSync('old.txt', 'new.txt');"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on fs.rename"


class TestContrabandjsDetectsNetworkVariants:
    """Verify contraband_js.sh catches https and vm.run."""

    def test_detects_require_https(self):
        """contraband_js.sh must fail when require https found."""
        code = "const https = require('https');"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on require https"

    def test_detects_vm_run(self):
        """contraband_js.sh must fail when vm.run* found."""
        code = "vm.runInContext(code, context);"
        result = run_contraband_on_js(code)
        assert result.returncode != 0, "Should fail on vm.run"


class TestContrabandjsAllowsCleanCode:
    """Verify clean code passes contraband_js.sh."""

    def test_clean_code_passes(self):
        """Clean JS code should pass contraband check."""
        code = """
const fs = require('fs');
const path = require('path');

function loadSeed(filename) {
    const filepath = path.join(__dirname, 'seeds', filename);
    const content = fs.readFileSync(filepath, 'utf8');
    return JSON.parse(content);
}

console.log('Clean code');
"""
        result = run_contraband_on_js(code)
        assert result.returncode == 0, f"Clean code should pass: {result.stdout}"
