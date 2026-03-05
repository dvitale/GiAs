#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError

try:
    import curses
except Exception:
    curses = None


def run(cmd, timeout=2):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=timeout)
        return out.decode().strip()
    except Exception:
        return ""


def which(cmd):
    return shutil.which(cmd) is not None


def fmt_bytes(b):
    if b is None:
        return "?"
    b = float(b)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.1f}{unit}" if unit != "B" else f"{int(b)}{unit}"
        b /= 1024
    return f"{b:.1f}PB"


def fmt_rate(bps):
    if bps is None:
        return "?"
    return f"{fmt_bytes(bps)}/s"


def read_proc_uptime():
    try:
        with open("/proc/uptime", "r") as f:
            return float(f.read().split()[0])
    except Exception:
        return None


def read_proc_meminfo():
    data = {}
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                key, val = line.split(":", 1)
                data[key.strip()] = int(val.strip().split()[0]) * 1024
    except Exception:
        pass
    return data


def read_proc_loadavg():
    try:
        with open("/proc/loadavg", "r") as f:
            return f.read().strip().split()[:3]
    except Exception:
        return ["?", "?", "?"]


def read_cpu_usage(prev):
    try:
        with open("/proc/stat", "r") as f:
            parts = f.readline().split()
        vals = list(map(int, parts[1:]))
        idle = vals[3] + vals[4]
        total = sum(vals)
        if prev is None:
            return None, (total, idle)
        prev_total, prev_idle = prev
        dt = total - prev_total
        didle = idle - prev_idle
        if dt <= 0:
            return None, (total, idle)
        usage = (dt - didle) / dt * 100.0
        return usage, (total, idle)
    except Exception:
        return None, prev


def read_percpu(prev_list):
    try:
        with open("/proc/stat", "r") as f:
            lines = [ln for ln in f.readlines() if ln.startswith("cpu")][1:]
        usages = []
        new_prev = []
        for i, ln in enumerate(lines):
            parts = ln.split()[1:]
            vals = list(map(int, parts))
            idle = vals[3] + vals[4]
            total = sum(vals)
            if prev_list and i < len(prev_list):
                pt, pi = prev_list[i]
                dt = total - pt
                didle = idle - pi
                usage = (dt - didle) / dt * 100.0 if dt > 0 else 0.0
            else:
                usage = 0.0
            usages.append(usage)
            new_prev.append((total, idle))
        return usages, new_prev
    except Exception:
        return [], prev_list


def get_ollama_pid():
    out = run(["pgrep", "-xo", "ollama"])
    return out if out else None


def get_ps_fields(pid):
    if not pid:
        return None
    out = run(["ps", "-p", str(pid), "-o", "pid,pcpu,pmem,rss,vsz,nlwp,etime,cmd="])
    if not out:
        return None
    lines = out.splitlines()
    line = lines[-1]
    parts = line.split(maxsplit=7)
    if len(parts) < 8:
        return None
    return {
        "pid": parts[0],
        "pcpu": parts[1],
        "pmem": parts[2],
        "rss": int(parts[3]) * 1024,
        "vsz": int(parts[4]) * 1024,
        "nlwp": parts[5],
        "etime": parts[6],
        "cmd": parts[7],
    }


def read_proc_io(pid):
    try:
        with open(f"/proc/{pid}/io", "r") as f:
            data = {}
            for line in f:
                k, v = line.split(":")
                data[k.strip()] = int(v.strip())
            return data
    except Exception:
        return None


def read_net_dev():
    stats = {}
    try:
        with open("/proc/net/dev", "r") as f:
            lines = f.readlines()[2:]
        for ln in lines:
            if ":" not in ln:
                continue
            iface, rest = ln.split(":", 1)
            iface = iface.strip()
            if iface == "lo":
                continue
            parts = rest.split()
            rx_bytes = int(parts[0])
            tx_bytes = int(parts[8])
            stats[iface] = (rx_bytes, tx_bytes)
        return stats
    except Exception:
        return {}


def read_diskstats():
    stats = {}
    try:
        with open("/proc/diskstats", "r") as f:
            for ln in f:
                parts = ln.split()
                if len(parts) < 14:
                    continue
                name = parts[2]
                if name.startswith("loop") or name.startswith("ram"):
                    continue
                reads = int(parts[5])  # sectors read
                writes = int(parts[9])  # sectors written
                stats[name] = (reads, writes)
        return stats
    except Exception:
        return {}


def curl_json(url, timeout=1.5):
    try:
        req = Request(url)
        start = time.time()
        with urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        return data, (time.time() - start) * 1000.0
    except URLError:
        return None, None
    except Exception:
        return None, None


def get_ollama_ps():
    return curl_json("http://localhost:11434/api/ps")


def get_ollama_tags():
    return curl_json("http://localhost:11434/api/tags")


def list_installed_models():
    out = run(["ollama", "list"], timeout=3)
    if not out:
        return []
    lines = out.splitlines()[1:]
    models = []
    for line in lines:
        parts = line.split()
        if len(parts) >= 3:
            models.append((parts[0], parts[2]))
    return models


def count_active_connections():
    out = run(["ss", "-tnp"])
    if not out:
        return 0, 0, {}
    total = 0
    established = 0
    clients = {}
    for line in out.splitlines():
        if "ollama" in line and ":11434" in line:
            total += 1
            if "ESTAB" in line or "ESTABLISHED" in line:
                established += 1
            parts = line.split()
            if len(parts) >= 5:
                peer = parts[4]
                ip = peer.rsplit(":", 1)[0]
                clients[ip] = clients.get(ip, 0) + 1
    return total, established, clients


def get_nvidia_stats():
    if not which("nvidia-smi"):
        return None
    out = run([
        "nvidia-smi",
        "--query-gpu=name,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits",
    ])
    if not out:
        return None
    gpus = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 7:
            gpus.append({
                "name": parts[0],
                "util": parts[1],
                "mem_util": parts[2],
                "mem_used": parts[3],
                "mem_total": parts[4],
                "temp": parts[5],
                "power": parts[6],
            })
    return gpus


def get_rocm_stats():
    if not which("rocm-smi"):
        return None
    out = run(["rocm-smi", "--showuse", "--showmemuse", "--showtemp", "--showpower"], timeout=3)
    return out if out else None


def get_disk_usage(path):
    try:
        st = os.statvfs(path)
        total = st.f_frsize * st.f_blocks
        free = st.f_frsize * st.f_bavail
        used = total - free
        return total, used, free
    except Exception:
        return None


def color_for_pct(pct):
    if pct is None:
        return ""
    if pct < 50:
        return "G"
    if pct < 80:
        return "Y"
    return "R"


def tail_file(path, lines=5):
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = 1024
            data = b""
            while size > 0 and data.count(b"\n") <= lines:
                step = min(block, size)
                f.seek(-step, os.SEEK_CUR)
                data = f.read(step) + data
                f.seek(-step, os.SEEK_CUR)
                size -= step
            return data.decode(errors="replace").splitlines()[-lines:]
    except Exception:
        return []


def find_log_file():
    candidates = [
        os.path.expanduser("~/.ollama/logs/server.log"),
        "/var/log/ollama/ollama.log",
        "/var/log/ollama/server.log",
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


class HTUI:
    def __init__(self, stdscr, interval):
        self.stdscr = stdscr
        self.interval = interval
        self.prev_cpu = None
        self.prev_percpu = None
        self.prev_net = None
        self.prev_disk = None
        self.prev_io = None
        self.cache = {}
        self.log_path = find_log_file()
        self._init_curses()

    def _init_curses(self):
        curses.curs_set(0)
        self.stdscr.nodelay(True)
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(2, curses.COLOR_YELLOW, -1)
            curses.init_pair(3, curses.COLOR_RED, -1)
            curses.init_pair(4, curses.COLOR_BLUE, -1)

    def _color(self, key):
        if not curses.has_colors():
            return 0
        if key == "G":
            return curses.color_pair(1)
        if key == "Y":
            return curses.color_pair(2)
        if key == "R":
            return curses.color_pair(3)
        if key == "B":
            return curses.color_pair(4)
        return 0

    def safe_addstr(self, y, x, text, attr=0):
        """Scrive in modo sicuro sul terminale, gestendo i limiti dello schermo"""
        try:
            maxy, maxx = self.stdscr.getmaxyx()
            if y >= maxy - 1 or x >= maxx - 1 or y < 0 or x < 0:
                return False
            # Tronca il testo se supera i confini
            max_len = maxx - x - 1
            if max_len <= 0:
                return False
            text = str(text)[:max_len]
            self.stdscr.addstr(y, x, text, attr)
            return True
        except Exception:
            return False

    def draw_bar(self, y, x, width, pct, label):
        maxy, maxx = self.stdscr.getmaxyx()
        # Verifica limiti verticali
        if y >= maxy - 1 or y < 0:
            return
        if width < 10:
            return
        bar_w = width - len(label) - 8
        bar_w = max(10, bar_w)
        filled = int(bar_w * (pct / 100.0)) if pct is not None else 0
        color = self._color(color_for_pct(pct))

        if not self.safe_addstr(y, x, f"{label} "):
            return
        if not self.safe_addstr(y, x + len(label) + 1, "["):
            return
        if filled > 0:
            self.safe_addstr(y, x + len(label) + 2, "|" * filled, color)
        if filled < bar_w:
            self.safe_addstr(y, x + len(label) + 2 + filled, " " * (bar_w - filled))
        self.safe_addstr(y, x + len(label) + 2 + bar_w, "]")
        if pct is not None:
            self.safe_addstr(y, x + len(label) + 4 + bar_w, f" {pct:5.1f}%", color)

    def _rate_from_prev(self, curr, prev):
        if curr is None or prev is None:
            return None
        return max(0, curr - prev) / self.interval

    def _net_rate(self):
        curr = read_net_dev()
        if not curr or self.prev_net is None:
            self.prev_net = curr
            return None
        rx = sum(v[0] for v in curr.values())
        tx = sum(v[1] for v in curr.values())
        prx = sum(v[0] for v in self.prev_net.values())
        ptx = sum(v[1] for v in self.prev_net.values())
        self.prev_net = curr
        return self._rate_from_prev(rx, prx), self._rate_from_prev(tx, ptx)

    def _disk_rate(self):
        curr = read_diskstats()
        if not curr or self.prev_disk is None:
            self.prev_disk = curr
            return None
        r = sum(v[0] for v in curr.values())
        w = sum(v[1] for v in curr.values())
        pr = sum(v[0] for v in self.prev_disk.values())
        pw = sum(v[1] for v in self.prev_disk.values())
        self.prev_disk = curr
        # sectors are 512 bytes
        return self._rate_from_prev(r * 512, pr * 512), self._rate_from_prev(w * 512, pw * 512)

    def _proc_io_rate(self, pid):
        curr = read_proc_io(pid) if pid else None
        if not curr or self.prev_io is None:
            self.prev_io = curr
            return None
        r = curr.get("read_bytes")
        w = curr.get("write_bytes")
        pr = self.prev_io.get("read_bytes")
        pw = self.prev_io.get("write_bytes")
        self.prev_io = curr
        return self._rate_from_prev(r, pr), self._rate_from_prev(w, pw)

    def draw(self):
        self.stdscr.erase()
        maxy, maxx = self.stdscr.getmaxyx()

        # Controlla dimensione minima del terminale
        if maxy < 10 or maxx < 40:
            self.safe_addstr(0, 0, "Terminale troppo piccolo! Min 40x10")
            self.stdscr.refresh()
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        up = read_proc_uptime()
        load1, load5, load15 = read_proc_loadavg()
        cpu, self.prev_cpu = read_cpu_usage(self.prev_cpu)
        percpu, self.prev_percpu = read_percpu(self.prev_percpu)

        line = 0
        if not self.safe_addstr(line, 0, f"Ollama Monitor  |  {now}  |  Load {load1} {load5} {load15}"):
            return
        line += 1
        if line >= maxy - 1:
            return
        if up is not None:
            up_h = int(up // 3600)
            up_m = int((up % 3600) // 60)
            up_s = int(up % 60)
            self.safe_addstr(line, 0, f"Uptime: {up_h}h {up_m}m {up_s}s  |  Refresh: {self.interval:.1f}s")
        line += 2

        if line >= maxy - 1:
            return
        if cpu is not None:
            self.draw_bar(line, 0, maxx - 1, cpu, "CPU")
            line += 1
        if line >= maxy - 1:
            return
        if percpu:
            per_line = maxx // 18 if maxx > 40 else 2
            for i, v in enumerate(percpu[: min(len(percpu), 16)]):
                if line >= maxy - 2:
                    break
                if i % per_line == 0:
                    line += 1
                x = (i % per_line) * 18
                self.draw_bar(line, x, 18, v, f"C{i}")
            line += 2

        if line >= maxy - 1:
            return
        mem = read_proc_meminfo()
        if mem:
            total = mem.get("MemTotal")
            avail = mem.get("MemAvailable")
            used = total - avail if total and avail else None
            pct = (used / total * 100.0) if used and total else None
            self.draw_bar(line, 0, maxx - 1, pct if pct is not None else 0, "MEM")
            if used is not None and maxx > 26:
                self.safe_addstr(line, maxx - 26, f"{fmt_bytes(used)}/{fmt_bytes(total)}")
            line += 1

            if line >= maxy - 1:
                return
            swt = mem.get("SwapTotal")
            swf = mem.get("SwapFree")
            if swt and swf is not None:
                su = swt - swf
                sp = su / swt * 100.0 if swt else 0
                self.draw_bar(line, 0, maxx - 1, sp, "SWAP")
                if maxx > 26:
                    self.safe_addstr(line, maxx - 26, f"{fmt_bytes(su)}/{fmt_bytes(swt)}")
                line += 2

        if line >= maxy - 1:
            return
        rx_tx = self._net_rate()
        if rx_tx:
            rx, tx = rx_tx
            self.safe_addstr(line, 0, f"NET: RX {fmt_rate(rx)}  TX {fmt_rate(tx)}")
            line += 1

        if line >= maxy - 1:
            return
        dr = self._disk_rate()
        if dr:
            rr, wr = dr
            self.safe_addstr(line, 0, f"DISK IO: Read {fmt_rate(rr)}  Write {fmt_rate(wr)}")
            line += 2

        # Ollama process
        if line >= maxy - 1:
            return
        pid = get_ollama_pid()
        if not pid:
            self.safe_addstr(line, 0, "Ollama: NOT RUNNING", self._color("R"))
            line += 2
        else:
            psf = get_ps_fields(pid)
            self.safe_addstr(line, 0, f"Ollama PID {pid}", self._color("G"))
            line += 1
            if line >= maxy - 1:
                return
            if psf:
                cpu_p = float(psf["pcpu"])
                mem_p = float(psf["pmem"])
                self.safe_addstr(line, 0, f"CPU {cpu_p:.1f}%  MEM {mem_p:.1f}%  RSS {fmt_bytes(psf['rss'])}  VSZ {fmt_bytes(psf['vsz'])}")
                line += 1
                if line >= maxy - 1:
                    return
                self.safe_addstr(line, 0, f"Threads {psf['nlwp']}  Uptime {psf['etime']}")
                line += 1
                if line >= maxy - 1:
                    return
                cmd = psf["cmd"][: maxx - 1]
                self.safe_addstr(line, 0, f"Cmd: {cmd}")
                line += 1
            if line >= maxy - 1:
                return
            io_rate = self._proc_io_rate(pid)
            if io_rate:
                rr, wr = io_rate
                self.safe_addstr(line, 0, f"Proc IO: Read {fmt_rate(rr)}  Write {fmt_rate(wr)}")
                line += 1
            if line >= maxy - 1:
                return
            total_conn, estab, clients = count_active_connections()
            self.safe_addstr(line, 0, f"Connessioni 11434: {estab} attive, {total_conn} totali")
            line += 2

        # GPU
        if line >= maxy - 1:
            return
        gpus = get_nvidia_stats()
        if gpus:
            self.safe_addstr(line, 0, "GPU NVIDIA:", self._color("B"))
            line += 1
            for idx, g in enumerate(gpus):
                if line >= maxy - 2:
                    break
                used = float(g["mem_used"]) if g["mem_used"].isdigit() else None
                total = float(g["mem_total"]) if g["mem_total"].isdigit() else None
                pct = (used / total * 100.0) if used and total else None
                self.safe_addstr(line, 0, f"GPU{idx} {g['name']} | Util {g['util']}% | Mem {g['mem_util']}% | Temp {g['temp']}C | Power {g['power']}W")
                line += 1
                if line >= maxy - 1:
                    break
                if pct is not None:
                    self.draw_bar(line, 2, maxx - 3, pct, "VRAM")
                    line += 1
            line += 1
        else:
            rocm = get_rocm_stats()
            if rocm:
                self.safe_addstr(line, 0, "GPU AMD (rocm-smi):", self._color("B"))
                line += 1
                for ln in rocm.splitlines()[:4]:
                    if line >= maxy - 1:
                        break
                    self.safe_addstr(line, 0, ln[: maxx - 1])
                    line += 1
                line += 1

        # Models and API
        if line >= maxy - 1:
            return
        if time.time() - self.cache.get("installed_ts", 0) > 30:
            self.cache["installed"] = list_installed_models()
            self.cache["installed_ts"] = time.time()
        installed = self.cache.get("installed", [])

        ps_json, ps_ms = get_ollama_ps()
        tags_json, tags_ms = get_ollama_tags()

        self.safe_addstr(line, 0, "Modelli:", self._color("B"))
        line += 1
        if line >= maxy - 1:
            return
        if installed:
            self.safe_addstr(line, 0, "Installati: " + ", ".join([m[0] for m in installed[:5]]) + (" ..." if len(installed) > 5 else ""))
        else:
            self.safe_addstr(line, 0, "Installati: nessuno o comando non disponibile")
        line += 1

        if line >= maxy - 1:
            return
        if ps_json and ps_json.get("models"):
            models = ps_json["models"]
            names = [m.get("name", "?") for m in models]
            self.safe_addstr(line, 0, "Caricati: " + ", ".join(names[:4]) + (" ..." if len(names) > 4 else ""))
            line += 1
        else:
            self.safe_addstr(line, 0, "Caricati: nessuno" if ps_json else "Caricati: API non raggiungibile")
            line += 1

        if line >= maxy - 1:
            return
        total_conn, estab, clients = count_active_connections()
        if estab > 0:
            if ps_json and ps_json.get("models") and len(ps_json["models"]) == 1:
                active = ps_json["models"][0].get("name", "?")
                self.safe_addstr(line, 0, f"Attivo: {active}", self._color("G"))
            else:
                self.safe_addstr(line, 0, "Ollama sta servendo richieste", self._color("Y"))
        else:
            self.safe_addstr(line, 0, "Nessuna richiesta attiva", self._color("B"))
        line += 1

        if line >= maxy - 1:
            return
        if ps_ms is not None or tags_ms is not None:
            self.safe_addstr(line, 0, f"API latency: /ps {ps_ms:.0f}ms  /tags {tags_ms:.0f}ms" if ps_ms is not None and tags_ms is not None else "API latency: n/a")
            line += 2

        # Top clients
        if line >= maxy - 1:
            return
        if clients:
            top = sorted(clients.items(), key=lambda x: x[1], reverse=True)[:3]
            top_str = ", ".join([f"{ip}({cnt})" for ip, cnt in top])
            self.safe_addstr(line, 0, f"Top client: {top_str}")
            line += 2

        # Disk usage
        if line >= maxy - 1:
            return
        models_dir = os.environ.get("OLLAMA_MODELS", os.path.expanduser("~/.ollama"))
        for path, label in [("/", "Root"), (models_dir, "Modelli")]:
            if line >= maxy - 1:
                break
            du = get_disk_usage(path)
            if not du:
                continue
            total, used, free = du
            pct = used / total * 100.0 if total else 0
            self.draw_bar(line, 0, maxx - 1, pct, f"DISK {label}")
            if maxx > 26:
                self.safe_addstr(line, maxx - 26, f"{fmt_bytes(used)}/{fmt_bytes(total)}")
            line += 1
        line += 1

        # Logs
        if line >= maxy - 2:
            # Lascia spazio per il footer
            self.safe_addstr(maxy - 1, 0, "q per uscire | Ctrl+C per uscire | Terminale troppo piccolo, scorri in su")
            self.stdscr.refresh()
            return

        if self.log_path:
            self.safe_addstr(line, 0, f"Log tail ({self.log_path}):", self._color("B"))
            line += 1
            remaining_lines = maxy - line - 2  # Lascia spazio per footer
            for ln in tail_file(self.log_path, min(4, remaining_lines)):
                if line >= maxy - 2:
                    break
                self.safe_addstr(line, 0, ln[: maxx - 1])
                line += 1
        else:
            self.safe_addstr(line, 0, "Log: nessun file trovato", self._color("Y"))
            line += 1

        self.safe_addstr(maxy - 1, 0, "q per uscire | Ctrl+C per uscire")
        self.stdscr.refresh()

    def loop(self):
        while True:
            try:
                key = self.stdscr.getch()
                if key == ord("q"):
                    return
                self.draw()
                time.sleep(self.interval)
            except KeyboardInterrupt:
                return


def run_plain(interval):
    # Fallback non-tty: stampa una sola volta
    print("Ollama Monitor (plain mode)")
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    pid = get_ollama_pid()
    if pid:
        psf = get_ps_fields(pid)
        print(f"Ollama PID {pid}")
        if psf:
            print(f"CPU {psf['pcpu']}%  MEM {psf['pmem']}%  RSS {fmt_bytes(psf['rss'])}")
    else:
        print("Ollama non in esecuzione")


def main():
    parser = argparse.ArgumentParser(description="Monitor Ollama in tempo reale")
    parser.add_argument("-i", "--interval", type=float, default=2.0, help="Intervallo aggiornamento in secondi")
    args = parser.parse_args()

    if not sys.stdout.isatty() or curses is None:
        run_plain(args.interval)
        return

    curses.wrapper(lambda stdscr: HTUI(stdscr, args.interval).loop())


if __name__ == "__main__":
    main()
