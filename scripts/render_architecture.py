"""Build the editable architecture SVG and optionally export a presentation PNG.

Usage: python3 scripts/render_architecture.py [--png]
PNG export requires ImageMagick with its librsvg delegate. No network access.
"""

import argparse
from html import escape
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/assets'
WIDTH, HEIGHT = 2560, 1780
INK = '#172B42'
MUTED = '#5C6D80'
LINE = '#CED9E3'
TEAL = '#007E78'
BLUE = '#3269B4'
PURPLE = '#7754B5'
AMBER = '#B96914'
parts = []


def add(value):
    parts.append(value)


def rect(x, y, w, h, fill='white', stroke=None, radius=16, dash=None):
    attrs = f' stroke="{stroke}" stroke-width="2"' if stroke else ''
    if dash:
        attrs += f' stroke-dasharray="{dash}"'
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}"{attrs}/>')


def text(x, y, value, size=22, color=INK, weight=400, anchor='start', spacing=None, family='Open Sans'):
    letter = f' letter-spacing="{spacing}"' if spacing is not None else ''
    add(f'<text x="{x}" y="{y}" font-family="{family}, Arial, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}"{letter}>{escape(value)}</text>')


def lines(x, y, values, size=20, color=MUTED, gap=30, **kwargs):
    for index, value in enumerate(values):
        text(x, y + index * gap, value, size, color, **kwargs)


def path(d, color=TEAL, width=3, arrow=False, dash=None):
    more = f' marker-end="url(#{"arrow-teal" if color == TEAL else "arrow-muted"})"' if arrow else ''
    if dash:
        more += f' stroke-dasharray="{dash}"'
    add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" '
        f'stroke-linecap="round" stroke-linejoin="round"{more}/>')


def badge(x, y, value, color=TEAL):
    add(f'<circle cx="{x}" cy="{y}" r="19" fill="{color}" stroke="white" stroke-width="4"/>')
    text(x, y + 6, str(value), 19, 'white', 700, 'middle')


def icon(kind, x, y, color=TEAL, scale=1):
    add(f'<g transform="translate({x} {y}) scale({scale})" fill="none" stroke="{color}" '
        'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">')
    icons = {
        'user': '<circle cx="24" cy="13" r="9"/><path d="M7 43c0-12 7-18 17-18s17 6 17 18Z"/>',
        'api': '<rect x="3" y="6" width="42" height="35" rx="5"/><path d="M3 16h42M10 11h1m5 0h1m5 0h1M20 24l-6 5 6 5m9-10 6 5-6 5"/>',
        'worker': '<rect x="10" y="10" width="28" height="28" rx="5"/><path d="M18 0v10M30 0v10M18 38v10M30 38v10M0 18h10M0 30h10M38 18h10M38 30h10M20 18l10 6-10 6Z"/>',
        'model': '<path d="M24 4 43 15v20L24 46 5 35V15ZM5 15l19 11 19-11M24 26v20M14 10l19 11"/>',
        'shield': '<path d="M24 3 42 10v13c0 11-9 19-18 23C15 42 6 34 6 23V10ZM15 24l6 6 13-14"/>',
        'orders': '<rect x="6" y="4" width="36" height="40" rx="5"/><path d="M6 17h36M6 31h36M12 10h4m-4 14h4m-4 14h4M28 10h8m-8 14h8m-8 14h8"/>',
        'database': '<ellipse cx="24" cy="9" rx="19" ry="7"/><path d="M5 9v29c0 10 38 10 38 0V9M5 23c0 10 38 10 38 0"/>',
        'cluster': '<path d="m24 3 19 11v22L24 47 5 36V14Z"/><circle cx="24" cy="25" r="7"/><path d="M24 8v10m0 14v10M10 17l8 5m12 7 8 5M10 34l8-5m12-7 8-5"/>',
        'trace': '<path d="M5 9h27M13 21h30M13 9v12m8 0v15m0 0h17M5 43h16"/><circle cx="35" cy="9" r="3"/><circle cx="41" cy="36" r="3"/>',
        'metrics': '<path d="M5 5v38h39M13 35V25m10 10V15m10 20V8M10 16l10-7 10 3 13-9"/>',
        'dashboard': '<rect x="4" y="5" width="40" height="38" rx="4"/><path d="M4 17h40M19 17v26M10 11h1m5 0h1M26 35l5-7 5 3 4-8"/>',
        'logs': '<path d="M12 4h24l7 7v33H5V4h7M34 4v10h9M13 23h22M13 31h22M13 38h14"/>',
        'cloud': '<path d="M12 36a10 10 0 0 1-1-20 14 14 0 0 1 27 1 10 10 0 0 1 0 19ZM19 20l-5 6 5 6m10-12 5 6-5 6"/>',
        'git': '<circle cx="12" cy="9" r="5"/><circle cx="12" cy="39" r="5"/><circle cx="36" cy="12" r="5"/><path d="M12 14v20m24-17v4c0 9-24 1-24 12"/>',
        'terminal': '<rect x="3" y="7" width="42" height="34" rx="5"/><path d="m12 18 7 6-7 6m15 0h10"/>',
        'layers': '<path d="m24 4 21 11-21 11L3 15ZM3 25l21 11 21-11M3 35l21 11 21-11"/>',
        'helm': '<circle cx="24" cy="24" r="14"/><circle cx="24" cy="24" r="4"/><path d="M24 1v19m0 8v19M1 24h19m8 0h19M8 8l13 13m6 6 13 13M8 40l13-13m6-6L40 8"/>',
    }
    add(icons[kind])
    add('</g>')


def node(x, y, w, h, title, subtitle, symbol, color=TEAL, fill='white'):
    rect(x, y, w, h, fill, LINE, 14)
    rect(x + 20, y + 20, 60, 60, '#EFF6F6' if color == TEAL else '#F0ECF8', radius=12)
    icon(symbol, x + 30, y + 30, color, 0.83)
    text(x + 20, y + 114, title, 25, INK, 700)
    text(x + 20, y + 145, subtitle, 17, MUTED)


def build():
    parts.clear()
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">')
    add('<title id="title">Agentic DevOps — target architecture and execution workflow</title>')
    add('<desc id="desc">A local operator submits a diagnosis to the API. PostgreSQL holds jobs and history. A leased worker uses a simulated model adapter and authenticated tools to inspect an orders simulator. Restarts require approval and deduplication. The target includes Kubernetes, observability, infrastructure automation and CI. Bedrock is a future M2 integration. T05 runs separate Kubernetes services with network isolation; observability and AWS remain planned.</desc>')
    add('<defs><marker id="arrow-teal" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0 10 5 0 10Z" fill="#007E78"/></marker><marker id="arrow-muted" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0 10 5 0 10Z" fill="#8796A5"/></marker></defs>')
    rect(0, 0, WIDTH, HEIGHT, '#FFFFFF', radius=0)
    rect(0, 0, 16, HEIGHT, TEAL, radius=0)

    # Title and key: generous margins keep the image legible on a presentation slide.
    text(80, 69, 'AGENTIC DEVOPS PLATFORM LAB', 21, TEAL, 700, spacing=3)
    text(80, 142, 'From a question to an auditable action.', 53, INK, 700, family='Montserrat')
    text(80, 191, 'Diagnose a simulated service. Approve controlled actions. Investigate every execution.', 25, MUTED)
    rect(2080, 53, 400, 47, INK, radius=23)
    text(2280, 84, 'M1  /  TARGET ARCHITECTURE', 17, 'white', 700, 'middle', 1)
    path('M2090 141 H2134', arrow=True)
    text(2148, 148, 'Execution flow', 18, MUTED)
    path('M2310 141 H2354', PURPLE, 3, dash='7 6')
    text(2370, 148, 'Future', 18, MUTED)
    text(2080, 190, 'Current implementation: T05 Kubernetes lab', 17, MUTED)

    # Local machine boundary and nested Kubernetes namespaces.
    rect(80, 245, 1930, 1070, '#F7F9FC', LINE, 22)
    text(110, 286, 'LOCAL MACHINE', 17, MUTED, 700, spacing=2)
    rect(370, 310, 1608, 969, '#FFFFFF', '#AEBFCF', 16)
    icon('cluster', 394, 329, BLUE, 0.8)
    text(448, 359, 'Dedicated Minikube VM', 24, INK, 700)
    text(1945, 356, 'agentic-devops  /  QEMU + Calico', 19, MUTED, anchor='end')

    rect(398, 391, 903, 402, '#F2F8F8', '#BBD9D6', 12)
    text(420, 423, 'lab-app', 17, TEAL, 700)
    rect(1345, 391, 604, 402, '#F4F7FC', '#C4D2E8', 12)
    text(1367, 423, 'lab-tools', 17, BLUE, 700)
    rect(759, 922, 542, 157, '#F5F3FB', '#D5C9E7', 12)
    text(781, 951, 'lab-data', 17, PURPLE, 700)

    # Operator, applications and the model branch.
    icon('user', 160, 508, INK, 1.4)
    text(194, 613, 'Lab operator', 25, INK, 700, 'middle')
    text(194, 645, 'Local browser', 19, MUTED, anchor='middle')
    lines(194, 709, ['Request a diagnosis', 'Review evidence', 'Approve an action'], 18, MUTED, 29, anchor='middle')
    node(445, 565, 280, 168, 'Interface / API', 'Submit, poll and approve', 'api')
    node(990, 565, 280, 168, 'Agent worker', 'Lease, execute and persist', 'worker')
    node(1380, 565, 240, 168, 'Tool service', 'Authorize every call', 'shield', BLUE)
    node(1680, 565, 240, 168, 'Orders simulator', 'Health and restart', 'orders', BLUE)
    rect(990, 425, 280, 85, '#FFFFFF', '#BBD9D6', 12)
    icon('model', 1008, 443, TEAL, 0.85)
    text(1065, 460, 'Model adapter', 21, INK, 700)
    text(1065, 489, 'M1: scripted decisions', 16, MUTED)

    # Main flow: orthogonal paths avoid crossing the component cards.
    path('M278 599 H445', arrow=True)
    badge(360, 599, 1)
    text(360, 557, 'localhost', 17, MUTED, anchor='middle')
    path('M445 670 H278', arrow=True)
    badge(360, 670, 8)
    text(360, 711, 'result', 17, MUTED, anchor='middle')

    path('M585 733 V1009 H788', arrow=True)
    badge(585, 836, 2)
    lines(563, 881, ['Publish job', 'Read history'], 18, MUTED, 27, anchor='end')

    path('M1130 733 V966', arrow=True)
    badge(1130, 838, 3)
    text(1160, 844, 'Claim', 18, MUTED)
    badge(1130, 890, 7)
    text(1160, 896, 'Save evidence', 18, MUTED)

    path('M1130 565 V510', arrow=True)
    badge(1130, 539, 4)
    path('M1270 635 H1380', arrow=True)
    badge(1325, 635, 5)
    path('M1620 635 H1680', arrow=True)
    badge(1650, 635, 6)

    path('M1500 733 V1009 H1270', arrow=True)
    text(1530, 843, 'Approval binding', 19, BLUE, 600)
    text(1530, 873, '+ idempotency', 19, BLUE, 600)
    text(1530, 904, 'Checked before a new effect', 16, MUTED)

    path('M1800 733 V1067 H1316 V1037 H1270', arrow=True)
    text(1770, 1038, 'Atomic effect + result', 16, MUTED, anchor='end')

    # Queue / history storage.
    rect(789, 966, 482, 90, '#FFFFFF', '#D5C9E7', 10)
    icon('database', 807, 985, PURPLE, 0.9)
    text(871, 1001, 'PostgreSQL', 26, INK, 700)
    text(871, 1032, 'Jobs · events · approvals · tool results', 17, MUTED)

    # A concise approval note sits in the open central space.
    rect(760, 587, 190, 140, '#FFFFFF', '#BBD9D6', 12)
    text(855, 620, 'HUMAN GATE', 14, TEAL, 700, 'middle', 1)
    lines(855, 656, ['Restart requires', 'explicit approval'], 17, INK, 28, anchor='middle')
    path('M725 702 H760', '#8796A5', 2, dash='4 5')

    # Cross-cutting observability, inside the target cluster.
    rect(398, 1117, 1551, 135, '#F7F9FC', LINE, 12)
    text(420, 1146, 'lab-observability', 17, MUTED, 700)
    text(1925, 1146, 'Telemetry across API, worker, tools and simulator', 17, MUTED, anchor='end')
    items = [(425, 'trace', 'Traces', 'OTel Collector → Tempo'),
             (820, 'metrics', 'Metrics', 'Prometheus'),
             (1190, 'dashboard', 'Explore', 'Grafana dashboards'),
             (1590, 'logs', 'Logs', 'JSON · run_id · trace_id')]
    for x, symbol, title, subtitle in items:
        icon(symbol, x, 1176, MUTED, 0.9)
        text(x + 62, 1197, title, 21, INK, 700)
        text(x + 62, 1224, subtitle, 16, MUTED)

    # Side rail: reading guide and explicitly deferred AWS integration.
    rect(2040, 245, 440, 660, '#FFFFFF', LINE, 18)
    text(2070, 291, 'HOW TO READ THE FLOW', 18, INK, 700, spacing=1)
    text(2070, 325, 'One run, from request to result', 18, MUTED)
    steps = [
        ('Request', 'Choose a scenario and ask.'),
        ('Publish', 'Persist a job and return its ID.'),
        ('Claim', 'A worker acquires a timed lease.'),
        ('Decide', 'The adapter proposes a step.'),
        ('Authorize', 'Tools validate identity and scope.'),
        ('Inspect / act', 'Read health or approved restart.'),
        ('Record', 'Store evidence and the outcome.'),
        ('Review', 'Poll the run and inspect results.'),
    ]
    for i, (title, subtitle) in enumerate(steps):
        y = 375 + i * 63
        badge(2089, y, i + 1)
        text(2124, y - 4, title, 21, INK, 700)
        text(2124, y + 21, subtitle, 16, MUTED)

    rect(2040, 932, 440, 383, '#F8F5FD', '#BAA4D9', 18, '8 7')
    text(2070, 975, 'M2  /  FUTURE EXTENSION', 17, PURPLE, 700, spacing=1)
    icon('cloud', 2072, 1000, PURPLE, 1.05)
    text(2139, 1033, 'Amazon Bedrock', 26, INK, 700)
    lines(2070, 1085, ['Real model inference replaces', 'the scripted model behavior.'], 20, INK, 30)
    lines(2070, 1170, ['Restricted temporary credentials', 'Controlled egress and usage limits', 'Existing approval rules still apply'], 17, MUTED, 30)
    text(2070, 1280, 'AWS is not used by the current lab.', 16, PURPLE, 600)

    # Delivery is visually separate from per-request execution.
    rect(80, 1345, 2400, 233, '#F5F7FA', LINE, 18)
    text(110, 1386, 'BUILD & DELIVERY', 18, INK, 700, spacing=1.5)
    text(2450, 1386, 'Prepare once · deploy a validated revision · run many diagnoses', 20, MUTED, anchor='end')
    delivery = [
        ('git', 'GitHub Actions', 'Validate and build', 'CI'),
        ('terminal', 'Local operator', 'Select the validated revision', 'DEPLOYMENT'),
        ('terminal', 'Ansible', 'Prepare host and cluster', 'BOOTSTRAP'),
        ('layers', 'OpenTofu', 'Platform, policies, telemetry', 'INFRASTRUCTURE'),
        ('helm', 'Helm', 'Deploy application resources', 'APPLICATION'),
        ('cluster', 'Local lab', 'Verify scenarios and isolation', 'VERIFICATION'),
    ]
    for i, (symbol, title, subtitle, label) in enumerate(delivery):
        x = 110 + i * 397
        icon(symbol, x, 1420, BLUE, 0.9)
        text(x + 62, 1432, label, 12, MUTED, 700, spacing=1)
        text(x + 62, 1463, title, 23, INK, 700)
        text(x, 1510, subtitle, 17, MUTED)
        if i < 5:
            path(f'M{x + 335} 1451 H{x + 375}', '#8796A5', 2.5, True)
    text(110, 1550, 'NetworkPolicy: deny by default, allow required paths. Application authorization remains a separate control.', 18, MUTED)

    # Status footer prevents a target-state diagram from claiming completed deployment.
    text(80, 1632, 'IMPLEMENTATION BOUNDARY', 17, MUTED, 700, spacing=1.5)
    rect(80, 1652, 725, 66, '#EEF7F3', radius=10)
    text(100, 1678, 'BUILT LOCALLY  /  T01–T05', 15, TEAL, 700)
    text(100, 1704, 'Durable runs · Kubernetes · approval · network isolation', 17, INK)
    rect(825, 1652, 905, 66, '#F2F5FA', radius=10)
    text(845, 1678, 'PLANNED  /  T06–T08', 15, BLUE, 700)
    text(845, 1704, 'Correlated telemetry · dashboards · CI · full verification · scoped cleanup', 17, INK)
    rect(1750, 1652, 730, 66, '#FBF4E9', radius=10)
    text(1770, 1678, 'CURRENT EFFECT BOUNDARY', 15, AMBER, 700)
    text(1770, 1704, 'Orders commits the simulated effect and deduplication in PostgreSQL.', 17, INK)
    text(80, 1755, 'Separate workloads and restricted flows are deployed. Observability and real model inference remain planned.', 17, MUTED)
    text(2480, 1755, 'HLD 01  /  28 SEP 2026', 15, MUTED, 600, 'end', 1)
    add('</svg>')
    return '\n'.join(parts) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--png', action='store_true', help='Export a 2x PNG using ImageMagick/librsvg.')
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    svg = OUTPUT / 'architecture-overview.svg'
    svg.write_text(build())
    print(svg.relative_to(ROOT))
    if args.png:
        png = svg.with_suffix('.png')
        subprocess.run(['magick', '-background', 'white', '-density', '192', str(svg),
                        '-strip', str(png)], check=True)
        print(png.relative_to(ROOT))


if __name__ == '__main__':
    main()
