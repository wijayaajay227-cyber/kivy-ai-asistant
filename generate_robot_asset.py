import os
import cairosvg

SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
    <defs>
        <filter id="neon-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
        <style>
            @keyframes blink { 0%, 90%, 100% { transform: scaleY(1); } 95% { transform: scaleY(0.1); } }
            @keyframes pulse { 0%,100% { opacity:0.8 } 50% { opacity:1; filter: drop-shadow(0 0 8px #00ffcc);} }
            .robot-eye { transform-origin: center; animation: blink 4s infinite ease-in-out; }
            .neon-part { animation: pulse 2s infinite ease-in-out; }
        </style>
    </defs>
    <rect x="95" y="15" width="10" height="25" rx="5" fill="#4a5568" />
    <circle cx="100" cy="15" r="8" fill="#00ffcc" class="neon-part" filter="url(#neon-glow)" />
    <rect x="25" y="75" width="15" height="50" rx="6" fill="#2d3748" />
    <rect x="160" y="75" width="15" height="50" rx="6" fill="#2d3748" />
    <rect x="35" y="40" width="130" height="120" rx="28" fill="#1a202c" stroke="#4a5568" stroke-width="4" />
    <path d="M 60 40 L 140 40 L 130 65 L 70 65 Z" fill="#2d3748" />
    <rect x="50" y="75" width="100" height="45" rx="12" fill="#0f172a" stroke="#2d3748" stroke-width="2" />
    <ellipse class="robot-eye" cx="75" cy="97" rx="10" ry="10" fill="#00ffcc" filter="url(#neon-glow)" />
    <ellipse class="robot-eye" cx="125" cy="97" rx="10" ry="10" fill="#00ffcc" filter="url(#neon-glow)" />
    <g fill="#4a5568">
        <rect x="75" y="135" width="6" height="12" rx="2" />
        <rect x="87" y="135" width="6" height="16" rx="2" />
        <rect x="99" y="135" width="6" height="16" rx="2" />
        <rect x="111" y="135" width="6" height="16" rx="2" />
        <rect x="123" y="135" width="6" height="12" rx="2" />
    </g>
</svg>'''

assets_dir = os.path.join(os.path.dirname(__file__), 'assets')
os.makedirs(assets_dir, exist_ok=True)
output_path = os.path.join(assets_dir, 'robot_logo.png')

try:
    cairosvg.svg2png(bytestring=SVG.encode('utf-8'), write_to=output_path, output_width=58, output_height=58)
    print('Wrote', output_path)
except Exception as e:
    print('Failed to write asset:', e)
