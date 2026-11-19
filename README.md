# ⚡ SkillSwap — Modern Peer-to-Peer Learning & Skill Exchange Ecosystem

[![Production Deployment](https://img.shields.io/badge/Deployed-Vercel-black?style=for-the-badge&logo=vercel)](https://github.com/SURYA00714/Skillswap)
[![Python Version](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Framework-Flask_3.x-red?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com/)
[![Database](https://img.shields.io/badge/Database-SQLite_%7C_PostgreSQL-green?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)
[![Theme Support](https://img.shields.io/badge/Theme-Dark_%26_Light_Mode-blueviolet?style=for-the-badge&logo=the-algorithms)](https://github.com/SURYA00714/Skillswap)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

> **Repository:** [https://github.com/SURYA00714/Skillswap](https://github.com/SURYA00714/Skillswap)  
> *"Teach what you love. Master what you dream."*

SkillSwap is an open, peer-to-peer knowledge exchange platform designed to break down barriers to continuous education. Rather than paying expensive hourly fees for tutoring, members connect directly to exchange real-world skills, schedule 1-on-1 sessions, launch collaborative study groups, share digital learning assets, and message in real time.

---

## 📑 Table of Contents
1. [🌟 Key Highlights & Feature Matrix](#-key-highlights--feature-matrix)
2. [🧩 Standalone Modular Architecture (Live Server Suite)](#-standalone-modular-architecture-live-server-suite)
3. [📘 A-to-Z Study Guide with ELI10 Explanations](STUDY_GUIDE_A_TO_Z.md)
4. [📱 Mobile First & UI/UX Design](#-mobile-first--uiux-design)
5. [🌓 Dark & Light Theme Engine](#-dark--light-theme-engine)
6. [📖 The Complete Feature Suite](#-the-complete-feature-suite)
7. [🚀 Our Engineering Journey](#-our-engineering-journey)
8. [🏗️ System Architecture & Stack](#️-system-architecture--stack)
9. [💻 Local Development & Setup](#-local-development--setup)
10. [☁️ Production Deployment on Vercel](#️-production-deployment-on-vercel)
11. [📡 API Reference](#-api-reference)
12. [👥 Community & License](#-community--license)

---

## 🧩 Standalone Modular Architecture (Live Server Suite)

SkillSwap now features a completely standalone, modular directory in `modules/` allowing each platform component to be executed individually in **Live Server**, static hosting, or local file viewing with zero backend dependencies:

| Module Directory | Key Capabilities | Standalone Entrypoint |
| :--- | :--- | :--- |
| **`modules/user_authentication/`** | User registration with strength meter, sign in, forgot password, 2FA toggle, active devices, and logout. | [user_authentication.html](modules/user_authentication/user_authentication.html) |
| **`modules/user_profile_management/`** | Personal information management, career details, education, avatar upload, and real-time live preview card. | [user_profile_management.html](modules/user_profile_management/user_profile_management.html) |
| **`modules/skill_management/`** | Manage offered teaching skills with proficiency tags and wanted learning goals with priority levels. | [skill_management.html](modules/skill_management/skill_management.html) |
| **`modules/skill_search_and_matching/`** | Instant search, category filters, and 100% reciprocal match detection algorithm. | [skill_search_and_matching.html](modules/skill_search_and_matching/skill_search_and_matching.html) |
| **`modules/skill_swap_request/`** | Dispatch swap proposals with introductory notes; filter tabs for All, Pending, Accepted, Declined. | [skill_swap_request.html](modules/skill_swap_request/skill_swap_request.html) |
| **`modules/communication/`** | Peer messaging with chat history, responsive bubbles, and 1-on-1 video session booking. | [communication.html](modules/communication/communication.html) |
| **`modules/feedback_and_admin/`** | 1–5 star rating submission, platform health KPI analytics, and admin moderation queue. | [feedback_and_admin.html](modules/feedback_and_admin/feedback_and_admin.html) |

> 💡 **Quick Launch:** Open [`modules/index.html`](modules/index.html) in VS Code **Live Server** or run `cd modules && python3 -m http.server 5500` to access the master navigation hub.

---

## 🌟 Key Highlights & Feature Matrix

| Feature | Description | Status |
| :--- | :--- | :---: |
| **Smart Skill Matcher** | Jaccard-similarity matching engine prioritizing 100% reciprocal swaps | ✅ Active |
| **Learning Sessions & Study Groups** | Create public learning rooms, schedule 1-on-1 swaps, or launch multi-student study groups with meet links | ✅ Active |
| **Resource Library Hub** | Upload guides, code templates, or curated links with up to 500 MB support | ✅ Active |
| **Real-Time Direct Messaging** | Seamless peer messaging with typing indicators, message search, and unread badges | ✅ Active |
| **Flicker-Free Smart Avatars** | Deterministic initial-letter SVG generation keyed to user email credentials | ✅ Active |
| **Granular Privacy Controls** | Choose exactly what contact details and social links are publicly visible | ✅ Active |
| **Dark / Light Theme Toggle** | Single-click theme switcher with instant local storage persistence across all pages | ✅ Active |
| **Zero-Skill (One-Way) Swap Mode** | Beginners with no skills to offer can still request mentorship gracefully | ✅ Active |

---

## 📱 Mobile First & UI/UX Design

The application is engineered with a strict **Mobile-First Responsive Architecture**:
- **Zero Horizontal Shifting**: All containers use dynamic max-widths (`minmax()`, flex wraps, and CSS clamp typography).
- **Responsive Navigation Drawer**: An animated hamburger menu slides down smoothly on mobile devices with touch-friendly tap targets (`min-height: 44px`).
- **Input & Modal Touch Optimization**: Form fields default to 16px font sizes to eliminate iOS and Android auto-zoom and input distortion.
- **Adaptive Action Cards**: Sessions, library items, and swap cards transform from horizontal desktop rows into clean vertical card stacks on screens below 768px.

---

## 🌓 Dark & Light Theme Engine

SkillSwap features a built-in, lightweight theme engine configured via CSS variables and localized storage:
- **Instant Toggle**: Located in every navigation bar and sidebar header (`.theme-toggle-btn`).
- **Zero Flash of Unstyled Theme (FOUT)**: Theme preference is read synchronously from `localStorage` before DOM render.
- **Curated HSL Palette**:
  - **Light Mode**: High-contrast, clean slate aesthetic (`#f8fafc` background, crisp borders, dark blue primary accents).
  - **Dark Mode**: OLED-friendly navy dark mode (`#0f172a` base, `#1e293b` surfaces, illuminated text, and soft glowing badges).

---

## 📖 The Complete Feature Suite

### 1. 🎯 Smart Matching Engine (`/smart-matches`)
- Computes match compatibility between what you **offer** vs. what others **want**.
- **Reciprocal Swap Priority**: Highlights bidirectional swaps where both learners can mutually teach each other.
- Filters by minimum score (High 70%+, Medium 40%+) and offers instant 1-click swap requests.

### 2. 📅 Learning Sessions & Study Groups (`/sessions`)
- **Public & Private Sessions**: Set title, scheduled time, duration, and Google Meet/Zoom links.
- **Collaborative Study Groups**: Create peer circles with member limits and topic tags.
- **Lifecycle Management**: View upcoming, completed, and missed sessions with live status updating.
- **Batch Actions**: Edit active sessions, delete individual cards, or clear completed history in one click.

### 3. 📚 Resource Library Hub (`/library`)
- Community knowledge repository for PDF guides, cheatsheets, project templates, and study links.
- Instant search and category filtering (Programming, Design, Languages, Business, Academics, Other).
- Robust download counters and file size formatters.

### 4. 💬 Peer Messaging System (`/messages`)
- Split-pane conversation interface with quick user search.
- Clean message bubbles with timestamp formatting and automated avatar fallbacks.
- Fully synchronized across active sessions.

### 5. 🛡️ User Profile & Privacy Suite (`/profile`)
- Comprehensive edit and view modes with dedicated **Save Changes** and **Discard** triggers.
- Gender selection for improved match personalization.
- Granular visibility checkboxes (Show/Hide Email, Phone, Social Profiles, Availability).

---

## 🚀 Our Engineering Journey

Building SkillSwap was a deliberate journey of transforming a classroom concept into a production-grade web application:

1. **Phase 1: Foundation & Auth Architecture**
   - Implemented Flask application factory with Blueprint isolation and session management.
   - Designed clean login and registration flows with credential validation.

2. **Phase 2: Avatar & UI Modernization**
   - Solved profile image blinking and shuttering by implementing deterministic SVG letter avatars keyed to the user's email address.
   - Built a single-shot error handler (`data-failed="true"`) to ensure zero broken image states.

3. **Phase 3: The Swap Ecosystem & Inclusivity**
   - Refactored swap workflows to remove rigid partner requirements.
   - Introduced one-way swap capabilities so complete beginners with no skills can still seek mentorship.

4. **Phase 4: Collaborative Learning Hubs**
   - Built the Learning Sessions and Study Group scheduling engine with dynamic meeting links.
   - Engineered the 500 MB Resource Library Hub for digital educational materials.

5. **Phase 5: Cloud Deployment & Serverless Optimization**
   - Resolved Vercel's read-only serverless constraints by piping temporary file stores and SQLite databases into `/tmp` with resilient in-memory caching.
   - Added seamless dark/light theme switching and full mobile viewport tuning.

---

## 🏗️ System Architecture & Stack

```
SwapSkills/
├── app/
│   ├── __init__.py           # Application factory with /tmp serverless fallbacks
│   ├── routes.py             # Core routes, auth, smart matches, sessions & library
│   ├── models.py             # SQLAlchemy schemas (User, SwapRequest, Session, LibraryItem)
│   ├── firebase_config.py    # Compatibility layer with local/serverless backing
│   ├── templates/            # Jinja2 responsive templates (Dark/Light enabled)
│   │   ├── index.html        # Main explore feed with search & filters
│   │   ├── smart_matches.html# Match recommendation dashboard
│   │   ├── sessions.html     # Learning sessions & study group manager
│   │   ├── library.html      # Digital resource sharing hub
│   │   ├── messages.html     # Real-time peer chat
│   │   ├── profile.html      # Profile customization & privacy settings
│   │   ├── seeRequest.html   # Incoming/Outgoing swap request management
│   │   └── landing.html      # Engaging landing page
│   └── static/
│       ├── css/              # Modular styles (index.css, messages.css, seeRequest.css)
│       ├── js/               # theme.js, index.js, messages.js, profile.js
│       └── default-profile.svg # High-contrast vector avatar fallback
├── run.py                    # WSGI entrypoint for Vercel and local server
├── vercel.json               # Vercel Python serverless build routing
├── requirements.txt          # Python dependencies
└── README.md                 # Complete documentation
```

---

## 💻 Local Development & Setup

### Prerequisites
- Python 3.10+
- Git

### Installation
```bash
# 1. Clone the repository
git clone https://github.com/SURYA00714/Skillswap.git
cd Skillswap

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the development server
python run.py
```
Open **`http://127.0.0.1:5000`** in your browser.

---

## ☁️ Production Deployment on Vercel

The repository is pre-configured with [`vercel.json`](vercel.json) for instant deployment:

1. Push your repository to GitHub.
2. Go to **[vercel.com/new](https://vercel.com/new)** and import your `Skillswap` repository.
3. Configure Environment Variables:
   - `SECRET_KEY` = `your-secure-random-key`
   - `MAX_CONTENT_LENGTH_MB` = `500`
   - `DATABASE_URL` = *(Optional: Supabase/Neon PostgreSQL connection string for persistent cloud data)*
4. Click **Deploy**.

---

## 📡 API Reference

### Sessions & Study Groups
- `GET /api/sessions` — Fetch user's sessions & study groups
- `POST /api/sessions` — Create a new learning session or study group
- `PUT /api/sessions/<id>` — Update session details or meeting link
- `DELETE /api/sessions/<id>` — Delete a specific session
- `POST /api/sessions/batch-delete` — Bulk delete or clear completed history

### Resource Library
- `GET /api/library` — Retrieve filtered educational resources
- `POST /api/library` — Upload a document/guide (up to 500 MB) or share an external link
- `GET /library/download/<id>` — Download resource with counter tracking

### Smart Matching
- `GET /api/smart-matches` — Calculate compatibility scores for active user

---

## 👥 Community & License

Built with ❤️ for passionate learners everywhere.  
Distributed under the **MIT License**. See `LICENSE` for details.
