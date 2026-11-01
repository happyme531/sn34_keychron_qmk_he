# /// script
# dependencies = ["websocket-client"]
# ///
"""Apply a narrow compatibility fix to workspace-owned Launcher browser tabs."""
import argparse
import json
import os
from pathlib import Path
import time
from urllib.request import urlopen
import websocket


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=19368)
    parser.add_argument("--watch", action="store_true", help="Keep the patch active on reloads and new tabs")
    args = parser.parse_args()
    if args.watch:
        return watch(args.port)
    script = Path(__file__).with_name("launcher_compat.js").read_text(encoding="utf-8")
    deadline = time.monotonic() + 15
    while True:
        try:
            with urlopen(f"http://127.0.0.1:{args.port}/json/list", timeout=2) as response:
                tabs = [p for p in json.load(response) if p.get("type") == "page" and
                        p.get("url", "").startswith("https://launcher.keychron.com/")]
            if tabs: break
        except OSError:
            pass
        if time.monotonic() >= deadline: raise RuntimeError("Workspace Launcher browser is unavailable")
        time.sleep(0.2)
    results = []
    for tab in tabs:
        connection = websocket.create_connection(tab["webSocketDebuggerUrl"], suppress_origin=True, timeout=5)
        request_id = 0
        def call(method, params):
            nonlocal request_id
            request_id += 1
            connection.send(json.dumps(dict(id=request_id, method=method, params=params)))
            while True:
                message = json.loads(connection.recv())
                if message.get("id") == request_id:
                    if "error" in message: raise RuntimeError(message["error"])
                    return message.get("result", {})
        try:
            # One-shot mode patches the current document. --watch retains the
            # CDP session required for init scripts to survive a page reload.
            call("Page.addScriptToEvaluateOnNewDocument", dict(source=script))
            result = call("Runtime.evaluate", dict(expression=script, returnByValue=True))
            if "exceptionDetails" in result: raise RuntimeError(result["exceptionDetails"])
            results.append(dict(url=tab["url"], result=result.get("result", {}).get("value")))
        finally:
            connection.close()
    print(json.dumps(results, indent=2))


def watch(port):
    script = Path(__file__).with_name("launcher_compat.js").read_text(encoding="utf-8")
    state = Path(__file__).resolve().parents[1] / "build/launcher_compat_worker.json"
    clients = {}
    failures = 0
    def call(client, method, params):
        client[1] += 1
        client[0].send(json.dumps(dict(id=client[1], method=method, params=params)))
        while True:
            message = json.loads(client[0].recv())
            if message.get("id") == client[1]:
                if "error" in message: raise RuntimeError(message["error"])
                return message.get("result", {})
    try:
        while failures < 5:
            try:
                with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2) as response:
                    tabs = [p for p in json.load(response) if p.get("type") == "page" and
                            p.get("url", "").startswith("https://launcher.keychron.com/")]
                failures = 0
            except OSError:
                failures += 1; time.sleep(1); continue
            ids = {tab["id"] for tab in tabs}
            for key in list(clients):
                if key not in ids: clients.pop(key)[0].close()
            results = []
            for tab in tabs:
                key = tab["id"]
                try:
                    if key not in clients:
                        clients[key] = [websocket.create_connection(tab["webSocketDebuggerUrl"],
                            suppress_origin=True, timeout=3), 0]
                        call(clients[key], "Page.addScriptToEvaluateOnNewDocument", dict(source=script))
                    result = call(clients[key], "Runtime.evaluate", dict(expression=script, returnByValue=True))
                    results.append(dict(id=key, url=tab["url"], result=result.get("result", {}).get("value")))
                except (OSError, RuntimeError, websocket.WebSocketException):
                    client = clients.pop(key, None)
                    if client: client[0].close()
            state.write_text(json.dumps(dict(pid=os.getpid(), port=port, tabs=results), indent=2), encoding="utf-8")
            time.sleep(1)
    finally:
        for client in clients.values(): client[0].close()


if __name__ == "__main__": main()
