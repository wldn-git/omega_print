# Hardware Disconnect Alarm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Menampilkan popup alarm modal di tengah layar ketika koneksi Printer Omega atau Scanner Keyence (Sisi A / Sisi B) terputus tiba-tiba, dilengkapi tombol "Coba Hubungkan Ulang" dan "Tutup".

**Architecture:** 
- Menambahkan modal dialog `show_hardware_alarm_popup(device_type)` di `main.py` yang dipanggil secara thread-safe via `self.root.after`.
- Menerapkan single-instance guard `self._active_alarm_popups = set()` untuk mencegah dialog bertumpuk saat interval watchdog polling berjalan.
- Mengintegrasikan sinyal alarm pada transisi status offline di watchdog printer dan thread listener scanner (dengan pengecualian pemutusan manual oleh operator).
- Menambahkan tombol aksi "Coba Hubungkan Ulang" (memanggil `test_tcp` untuk printer atau `connect_scanner` untuk scanner) dan tombol "Tutup".

**Tech Stack:** Python 3, Tkinter (`Toplevel`, `Label`, `Frame`, `Button`, `bell()`), `i18n.py`.

**Spec:** Desain konsisten tema industri Omega Batch App (header merah peringatan `#dc2626`, latar belakang Slate `#f8fafc`, kartu info perangkat dengan badge status, tombol aksi responsif).

## Global Constraints
- Target branch: `ver3.0`.
- Judul dialog dan komponen teks harus bilingual via `i18n.py` (Indonesia dan Inggris).
- Tidak boleh memblokir thread background socket (semua manipulasi UI via `self.root.after`).
- Pemutusan koneksi yang disengaja oleh operator (tombol Putuskan) TIDAK boleh memicu alarm.

## Review Focus
1. Guard anti-spam: jika koneksi printer terputus dan dialog belum ditutup, watchdog (setiap 3 detik) tidak boleh membuka popup baru.
2. Centering: dialog harus berada tepat di tengah window utama aplikasi (`self.root`).
3. Audio feedback: memanggil `self.root.bell()` saat alarm muncul.
4. Retry action: menekan "Coba Hubungkan Ulang" menutup dialog lalu memicu fungsi koneksi ulang perangkat terkait.
5. Dismiss action: menekan "Tutup" menutup dialog dengan bersih dan melepaskan modal grab.

---

### Task 1: Add i18n Translation Keys for Hardware Disconnect Alarm

**Files:**
- Modify: `i18n.py`

**Steps:**
- [ ] Add keys `alarm_hw_title`, `alarm_hw_subtitle`, `alarm_hw_desc`, `alarm_hw_detected_at`, `btn_retry_connect`, `btn_dismiss_alarm`, `dev_name_printer`, `dev_name_scanner1`, `dev_name_scanner2` in `LANG_ID` and `LANG_EN`.
- [ ] Verify dictionary integrity.

---

### Task 2: Implement Hardware Disconnect Alarm Popup in `main.py`

**Files:**
- Modify: `main.py`

**Steps:**
- [ ] In `OmegaBatchApp.__init__`, initialize `self._active_alarm_popups = set()`, `self._manual_disconnect_s1 = False`, `self._manual_disconnect_s2 = False`.
- [ ] Implement `show_hardware_alarm_popup(self, device_type)`:
  - Check if `device_type` already in `self._active_alarm_popups`; if so, return early.
  - Add `device_type` to `self._active_alarm_popups`.
  - Trigger audio bell: `self.root.bell()`.
  - Create `Toplevel(self.root)`, styled with `#dc2626` header, device info card, status badge, description, and action buttons.
  - Position modal centered on `self.root`.
  - Connect "Coba Hubungkan Ulang" to trigger retry logic for printer or scanner.
  - Connect "Tutup" and window close protocol to dismiss cleanly and remove `device_type` from `self._active_alarm_popups`.

---

### Task 3: Hook Alarm Triggers into Watchdog & Scanner Threads

**Files:**
- Modify: `main.py`

**Steps:**
- [ ] In `_start_hardware_watchdog_thread`: when `prev_status and not is_online`, invoke `self.root.after(0, lambda: self.show_hardware_alarm_popup("printer"))`.
- [ ] In `listen_to_scanner`: when socket closes or exception occurs, check if not `_manual_disconnect_sX`, then invoke `self.root.after(0, lambda: self.show_hardware_alarm_popup(f"scanner{scanner_id}"))`.
- [ ] In `disconnect_scanner` and `disconnect_all_scanners`, mark manual disconnect flags so intentional disconnects don't trigger the alarm.
- [ ] In `connect_scanner`, reset manual disconnect flags.

---

### Task 4: Create Unit Tests for Hardware Alarm Popup

**Files:**
- Create: `test_hardware_alarm_popup.py`

**Steps:**
- [ ] Test popup creation and title/labels.
- [ ] Test anti-spam guard (prevent duplicate dialogs for same device).
- [ ] Test retry action callback for printer and scanner.
- [ ] Test dismissal and guard cleanup.
- [ ] Run test suite: `python -m unittest test_hardware_alarm_popup.py`.

---

### Task 5: Verify and Push to Git

**Steps:**
- [ ] Run full project test suite (`python -m unittest discover -s . -p "test_*.py"`).
- [ ] Commit and push to `origin/ver3.0`.

