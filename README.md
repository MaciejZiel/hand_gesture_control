# hand_gesture_control (MVP)

Minimalny projekt do sterowania gestami dloni z kamerki (Windows + Linux).

## Co jest zrobione

- Live podglad z kamerki + overlay landmarkow i panel statusu.
- Rozpoznawanie wielu gestow jednej dloni + gesty dwoch dloni (LEFT/RIGHT/BOTH/DUAL).
- Stabilizacja rozpoznawania (okno, czas, histereza) + cooldown.
- Mapowanie gest -> akcja klawiatury, makra (sekwencje, text, delay).
- Profile akcji i szybkie przelaczanie (UI/klawisze/CLI).
- Kalibracja progow kciuk/pinch zapisywana do `config.json`.
- Logowanie zdarzen do pliku.
- Tryb headless (bez okna) + autostart na Linux.
- Tryb pauzy i przeladowanie configu w locie.

## Instalacja

```
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

Srodowisko developerskie (testy):

```
pip install -r requirements-dev.txt
```

## Quick Start

1. Zainstaluj zaleznosci (`pip install -r requirements.txt`)
2. Pobierz model (jeśli pracujesz na Python 3.12/3.13)
3. Uruchom:

```
python -m hand_gesture_control --dry-run --backend tasks
```

## Uruchomienie

```
python -m hand_gesture_control
```

Tryb testowy (bez naciskania klawiszy):

```
python -m hand_gesture_control --dry-run
```

Tryb bez okna (dziala w tle):

```
python -m hand_gesture_control --headless
```

Start w pauzie:

```
python -m hand_gesture_control --paused
```

Zamknij okno: `q` albo `Esc`.

## MediaPipe backend

Domyslnie `backend=auto`:

- Jesli `mediapipe` ma `solutions`, uzywa starego API (najprostsze).
- Jesli nie ma `solutions`, uzywa `tasks` i wymaga modelu `hand_landmarker.task`.

Na Python 3.12/3.13 mediapipe zwykle nie zawiera `solutions`, wiec potrzebujesz modelu.
Ustaw `task_model_path` w `config.json` (domyslnie `models/hand_landmarker.task`) albo
podaj `--model`.

Przyklad pobrania modelu (Linux/macOS):

```
mkdir -p models
python - <<'PY'
import pathlib
import urllib.request

url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
path = pathlib.Path("models/hand_landmarker.task")
path.parent.mkdir(parents=True, exist_ok=True)
urllib.request.urlretrieve(url, path)
print("Saved", path)
PY
```

## Konfiguracja

Plik `config.json` w katalogu projektu.

Najwazniejsze pola:

- `gesture_to_action`: mapowanie gest -> klawisz
- `gesture_window_size` i `gesture_min_votes`: stabilizacja gestu
- `gesture_min_stable_time`, `gesture_min_frames`: czas i liczba klatek do uznania gestu
- `gesture_switch_multiplier`: dodatkowy czas przy zmianie gestu
- `gesture_unknown_timeout`: ile trzymac ostatni gest, gdy dlon znika
- `thumb_extended_ratio`, `pinch_ratio`, `thumb_up_down_threshold`: progi klasyfikacji
- `cooldown_seconds`: opoznienie miedzy wyzwoleniami
- `backend`: `auto` / `solutions` / `tasks`
- `task_model_path`: sciezka do `hand_landmarker.task` (dla `tasks`)
- `camera_width` / `camera_height`: wymuszenie rozdzielczosci kamery
- `max_num_hands`: 1 lub 2 (domyslnie 2)
- `headless`: `true`/`false` (uruchomienie bez okna)
- `start_paused`: start w trybie pauzy (nie wysyla akcji)
- `fullscreen`: `true`/`false` (pelny ekran)
- `windowed_fullscreen`: `true`/`false` (okno na caly ekran z widocznymi przyciskami)
- `windowed_margin`: ile pikseli odjac z wysokosci (na pasek okna)
- `display_width` / `display_height`: rozmiar wyswietlania (np. 2880x1800)
- `overlay_scale`: `auto` albo liczba (np. `1.0`, `1.2`) - skala UI
- `overlay_alpha`, `overlay_padding`, `overlay_line_gap`: wyglad panelu UI
- `landmark_scale`: skala ikon (punkty/linie dloni)
- `controls_enabled`: pokazuje przyciski na ekranie
- `controls_position`: `right` / `top-right` / `top-left`
- `controls_scale`, `controls_alpha`, `controls_margin`, `controls_gap`: wyglad przyciskow
- `active_profile`: aktywny profil (np. `default`)
- `profiles`: zestawy mapowan gestow na akcje
- `log_enabled`: zapis zdarzen do pliku
- `log_mode`: `actions` / `active` / `all`
- `log_path`: sciezka do logu (np. `logs/gesture_events.log`)

Przyklady akcji:

- `SPACE`, `LEFT`, `RIGHT`, `UP`, `DOWN`
- `M`
- `CTRL+SHIFT+P`
- `VOLUME_UP`, `VOLUME_DOWN` (dziala jesli system wspiera media keys)

Makra (sekwencje):

- `CTRL+L;TEXT:hello;ENTER`
- `DELAY:0.3;SPACE`

Mozesz tez uzyc listy w JSON:

```
"OPEN_PALM": ["CTRL+L", "TEXT:hello", "ENTER"]
```

## Gesty

- `OPEN_PALM`
- `FOUR_FINGERS`
- `FIST`
- `INDEX_UP`
- `TWO_FINGERS`
- `THREE_FINGERS`
- `ROCK` (wskazujacy + maly)
- `OK_SIGN`
- `PINCH`
- `THUMB_UP` / `THUMB_DOWN` (lub `THUMB` jako fallback)

Gesty dwoch dloni:

- gdy obie dlonie maja ten sam stabilny gest, aktywny gest ma nazwe `BOTH_<GESTURE>`
  (np. `BOTH_OPEN_PALM`, `BOTH_FIST`).
- gdy obie dlonie maja rozne gesty: `DUAL_<LEFT>_<RIGHT>` (np. `DUAL_FIST_OPEN_PALM`)
- gdy tylko jedna dlon jest stabilna przy dwoch widocznych: `LEFT_<GESTURE>` albo `RIGHT_<GESTURE>`

## Profile

Mozesz miec wiele profilow (np. Spotify/YouTube/Prezentacja).

Przyklad w `config.json`:

```
"active_profile": "default",
"profiles": {
  "default": {
    "gesture_to_action": { "OPEN_PALM": "SPACE" }
  },
  "spotify": {
    "gesture_to_action": { "OPEN_PALM": "SPACE", "TWO_FINGERS": "LEFT" }
  }
}
```

Przelaczanie profili:

- klawisz `p` (cykl)
- klawisze `1-9` (wybor profilu po kolejnosci)
- przycisk `PROF` na ekranie (jesli `controls_enabled=true`)
- `--profile nazwa` przy uruchomieniu

Szybkie sterowanie:

- `s` — pauza/wznowienie akcji
- `r` — przeladowanie `config.json` w locie

Przyciski w UI:

- `PAUSE` / `RUN` — pauza/wznowienie
- `CFG` — przeladowanie konfiguracji

## Logowanie

Wlacz w `config.json`:

```
"log_enabled": true,
"log_mode": "actions",
"log_path": "logs/gesture_events.log"
```

## Kalibracja

Szybka kalibracja progow (kciuk i pinch) i zapis do `config.json`:

```
python -m hand_gesture_control --calibrate --backend tasks
```

W trakcie:
- pokaz otwarta dlon z kciukiem
- pokaz pinch (kciuk + wskazujacy)

Przerwanie: `q` lub `Esc`.

## Testy

```
pytest
```

## Lint/format (opcjonalnie)

```
ruff .
black .
```

## Autostart (Linux)

Skrypty w `scripts/`:

```
chmod +x scripts/install_autostart_linux.sh
./scripts/install_autostart_linux.sh
```

Usuniecie:

```
chmod +x scripts/remove_autostart_linux.sh
./scripts/remove_autostart_linux.sh
```
