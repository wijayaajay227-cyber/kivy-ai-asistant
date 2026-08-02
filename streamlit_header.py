import streamlit as st


def get_robot_logo_html():
    """Menghasilkan kode SVG interaktif dengan animasi CSS untuk logo web"""
    svg_code = """
    <div style="display: flex; justify-content: center; align-items: center; padding: 20px; background: #0d1117; border-radius: 12px; max-width: 250px; margin: auto;">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="100%" height="100%">
            <defs>
                <!-- Efek Glow / Neon untuk Mata -->
                <filter id="neon-glow" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="4" result="blur" />
                    <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
                
                <!-- Animasi Mata Berkedip & Menyala -->
                <style>
                    @keyframes blink {
                        0%, 90%, 100% { transform: scaleY(1); }
                        95% { transform: scaleY(0.1); }
                    }
                    @keyframes pulse {
                        0%, 100% { opacity: 0.8; }
                        50% { opacity: 1; filter: drop-shadow(0 0 8px #00ffcc); }
                    }
                    .robot-eye {
                        transform-origin: center;
                        animation: blink 4s infinite ease-in-out;
                    }
                    .neon-part {
                        animation: pulse 2s infinite ease-in-out;
                    }
                </style>
            </defs>

            <!-- 1. Antena / Sensor Atas -->
            <rect x="95" y="15" width="10" height="25" rx="5" fill="#4a5568" />
            <circle cx="100" cy="15" r="8" fill="#00ffcc" class="neon-part" filter="url(#neon-glow)" />

            <!-- 2. Telinga / Samping Kepala -->
            <rect x="25" y="75" width="15" height="50" rx="6" fill="#2d3748" />
            <rect x="160" y="75" width="15" height="50" rx="6" fill="#2d3748" />

            <!-- 3. Struktur Utama Kepala -->
            <rect x="35" y="40" width="130" height="120" rx="28" fill="#1a202c" stroke="#4a5568" stroke-width="4" />
            
            <!-- Plat Dahi (Aksen Desain) -->
            <path d="M 60 40 L 140 40 L 130 65 L 70 65 Z" fill="#2d3748" />

            <!-- 4. Area Mata (Screen) -->
            <rect x="50" y="75" width="100" height="45" rx="12" fill="#0f172a" stroke="#2d3748" stroke-width="2" />

            <!-- 5. Mata Robot (Animasi) -->
            <ellipse class="robot-eye" cx="75" cy="97" rx="10" ry="10" fill="#00ffcc" filter="url(#neon-glow)" />
            <ellipse class="robot-eye" cx="125" cy="97" rx="10" ry="10" fill="#00ffcc" filter="url(#neon-glow)" />

            <!-- 6. Komponen Mulut / Kisi Udara -->
            <g fill="#4a5568">
                <rect x="75" y="135" width="6" height="12" rx="2" />
                <rect x="87" y="135" width="6" height="16" rx="2" />
                <rect x="99" y="135" width="6" height="16" rx="2" />
                <rect x="111" y="135" width="6" height="16" rx="2" />
                <rect x="123" y="135" width="6" height="12" rx="2" />
            </g>
        </svg>
    </div>
    """
    return svg_code


def main():
    # --- TAMPILAN WEB STREAMLIT ---
    st.set_page_config(page_title="Robot Web Logo", layout="centered")

    # Tempatkan logo di header
    st.components.v1.html(get_robot_logo_html(), height=120)

    st.title("🤖 Web Logo Dashboard")
    st.write("Contoh implementasi logo kepala robot futuristik langsung di dalam layout website:")

    # Memasukkan Logo ke dalam Sidebar (Umum untuk Logo Web)
    with st.sidebar:
        st.markdown("<h3 style='text-align: center; color: white;'>Navigation</h3>", unsafe_allow_html=True)
        st.components.v1.html(get_robot_logo_html(), height=220)
        st.write("---")
        st.button("Dashboard")
        st.button("Settings")

    # Memasukkan Logo di Halaman Utama
    st.subheader("Preview Logo Ukuran Besar")
    st.components.v1.html(get_robot_logo_html(), height=250)


if __name__ == '__main__':
    main()
