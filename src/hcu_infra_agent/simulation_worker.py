"""Isolated DCUSim worker; stdout carries JSON and diagnostics go to stderr."""
import contextlib
import hashlib
import inspect
import json
import sys
from pathlib import Path


def main():
    request = json.loads(Path(sys.argv[1]).read_text())
    with contextlib.redirect_stdout(sys.stderr):
        import dcusim
        function = dcusim.dcusim
        signature = inspect.signature(function)
        if any(k not in signature.parameters for k in request):
            raise ValueError('Arguments are unsupported by this DCUSim version')
        effective = signature.bind(**request)
        effective.apply_defaults()
        result = function(**request)
        config = Path(dcusim.resolve_model_json(request['model']))
    source = Path(inspect.getfile(function))
    output = {'result': result, 'effective_arguments': dict(effective.arguments),
              'backend': {'name': 'dcusim', 'version': dcusim.__version__,
                          'entry': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()},
              'model_config': {'path': str(config), 'sha256': hashlib.sha256(config.read_bytes()).hexdigest()}}
    def convert(value):
        if hasattr(value, 'tolist'): return value.tolist()
        if hasattr(value, 'item'): return value.item()
        raise TypeError('Non-JSON simulator output: ' + type(value).__name__)
    print(json.dumps(output, default=convert, allow_nan=False))


if __name__ == '__main__':
    main()
