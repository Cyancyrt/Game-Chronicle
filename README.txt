DUNGEON CHRONICLES - BATTLE MOTION EDITION
====================================
GAME ONLY | Solo tactical RPG | Python 3.10+

CARA BERMAIN (Windows)
1. Ekstrak semua file ZIP ke folder biasa.
2. Pastikan Python 3.10 atau lebih baru terpasang.
3. Klik dua kali PLAY.bat, atau buka CMD di folder ini dan ketik:
   python Start.py
   (Alternatif: py -3 Start.py)
Tidak perlu pip install, internet, model ML atau dataset.

Menu: 1 Continue, 2 New adventure, 3 Guide, 4 Exit, 5 Practice arena,
6 Motion gallery (lihat seluruh sprite dan animasi tanpa save).
Campaign: 10 lantai procedural (opsional --floors 5..50).
Arrow/WASD untuk bergerak; E berinteraksi / end turn dalam combat.
Saat battle: 1 Attack, 2 Skill, 3 Guard, 4 Heavy, 5 Item,
6 Interrupt, 7 Break object, 8 Log, 9 Flee, V Status.
Pilih target dengan arrow/WASD dan E, X untuk batal.
F mengganti fokus musuh / berpindah kandidat target saat aiming.
I membuka detail intent, status, koordinat, combo (jika ada) dan legenda.
T mengaktifkan atau menonaktifkan animasi.
Checkpoint tersimpan otomatis di saves/balanced_tactical.json.
Mulai game baru; save edisi lama tidak otomatis diimpor.

BASE STAT FINAL (HP / AC / ATK / DEX / MP / STA)
Swordsman  42 / 15 / 6 / 2 / 11 / 15
Lancer     36 / 14 / 5 / 3 /  8 / 16
Cleric     35 / 14 / 4 / 1 / 18 / 10
Mage       31 / 13 / 4 / 2 / 22 /  9
Rogue      31 / 14 / 5 / 4 /  8 / 14
Archer     32 / 13 / 5 / 4 /  8 / 13
Warrior    40 / 14 / 4 / 1 /  8 / 13

Base stat menggunakan kandidat surrogate_2302 dari final evaluation.
Skill, passive, weapon, leveling, loot, ekonomi, dan aturan campaign
asli dipertahankan. Campaign memakai 6 AP seperti edisi sebelumnya.
Practice arena memakai profil referensi 5 AP, limited supplies dan
profil tekanan per encounter yang dipakai dalam eksperimen level 5.
Empat mode: solo, mixed, objective, boss. Pilih lewat menu 5.
Bisa juga: python Start.py --arena --arena-level 5 --seed 620000

CATATAN BALANCING
Pada pengujian referensi terdahulu (level 5, Tactical + Defensive
Agent), class gap turun dari 31,25 menjadi 16,67 percentage points.
Ini bukan jaminan seluruh campaign, level, atau gaya pemain seimbang.
Campaign belum divalidasi ulang secara menyeluruh. Practice arena
menggunakan profil referensi, tetapi tidak membatasi giliran pemain
seperti batas evaluasi otomatis. Game tidak melakukan optimasi saat
bermain. Tidak ada kode atau data penelitian dalam ZIP ini.

BATTLE MOTION EDITION
=====================
- Tujuh sprite ASCII original untuk seluruh class, sepuluh jenis monster.
- Pose idle, wind-up, walk, strike, guard, hurt, down dan victory.
- Animasi berurutan: lunge, spear thrust, dash, shield bash, panah,
  magic projectile dan spell, heal, guard, gerak musuh, hit reaction.
- Frame baru digambar di tempat yang sama, tanpa library eksternal.
- Stage merupakan visualisasi sinematik dari aksi, bukan koordinat grid.
  Grid tetap menjadi acuan posisi, range, LOS dan telegraph. HP/MP/ST/AP
  pada akhir animasi berasal dari state engine, bukan perhitungan visual.
- Beberapa skill berbagi animasi dasar class dengan variasi projectile
  atau pola; tidak semua 28 skill memiliki koreografi yang unik.
- Gunakan Windows CMD / Windows Terminal dengan dukungan ANSI (VT).
  Rekomendasi minimal 100 kolom x 36 baris untuk HUD lengkap. Pada
  terminal pendek, stage statis disembunyikan agar grid lebih mudah dibaca;
  animasi aksi tetap tersedia pada terminal yang mendukung.
- Mode plain, no-clear, stdout redirect, atau terminal tanpa ANSI tidak
  memutar animasi agar output tidak berkedip atau memenuhi log.
- Animasi baru untuk tactical campaign dan practice arena. Mode --grid
  dan --classic tetap dapat dimainkan, namun UI battle lamanya dipertahankan.
- Tidak ada perubahan angka base stat, skill, AP, atau damage. Satu hook
  observer pada tactical.py mengambil snapshot sebelum/sesudah intent.

CARA MENCOBA
============
Klik PREVIEW_MOTION.bat untuk mencoba class tanpa memulai campaign.
Atau ketik di CMD:
  python Start.py --motion-gallery
  python Start.py --arena --seed 620000
  python Start.py --fast-animation
  python Start.py --no-animation
  python Start.py --plain

VALIDASI
========
84 skenario (7 role x 4 practice mode x 3 seed), level 5, maksimal 12 round:
trace engine sebelum dan sesudah observer identik, termasuk state RNG,
log, metrics, posisi, HP, resource, dan hasil. Ini uji regresi, bukan
validasi balancing ulang atau bukti seluruh campaign seimbang.
7 class dan 10 monster diuji dimensi frame. Layout diuji 24-118 kolom.
ANSI gallery 7 role, dan arena move / guard / end turn / toggle / flee
lulus uji interaktif pseudo-terminal Linux. Windows CMD belum diuji langsung.
