# Lokales Coding-Setup auf dem M5 MacBook Air 24 GB

**Ziel:** Am Ende kannst du lokal auf deinem M5 Air mit 24 GB RAM programmieren und zwischen zwei Modellen wechseln:

- **Qwen3.8-9B 4-bit** → schnell, wenig RAM, Daily Driver
- **Devstral Small 2 24B OptiQ 4-bit** → anspruchsvolle Coding- und Agent-Aufgaben

Wir verwenden **MLX/`mlx-lm`**, weil du Apple Silicon nutzt. `uv` verwaltet die Python-Umgebung.

**Wichtig:** Alle Shell-Befehle unten sind absichtlich **einzeilig**, damit du sie direkt kopieren kannst. Keine `\`-Zeilenfortsetzungen.

---

# 1. Ausgangszustand

Du hast bereits:

```bash
uv add mlx-lm
```

und MLX funktioniert.

Prüfen:

```bash
uv run python -c "import mlx; import mlx_lm; print('MLX funktioniert')"
```

Wenn `MLX funktioniert` erscheint, geht es weiter.

---

# 2. Modell 1: Qwen3.8-9B

Wir verwenden:

```text
keXjos/Qwen3.8-9B-mlx-4Bit
```

Die aktuelle MLX-Konvertierung ist etwa **5,04 GB** groß und basiert auf `empero-ai/Qwen3.8-9B`.

Für deinen 24-GB-Air ist das sehr angenehm: Es bleibt viel Unified Memory für macOS, VS Code, Kontext und andere Programme.

## Start

```bash
uv run mlx_lm.chat --model "keXjos/Qwen3.8-9B-mlx-4Bit" --max-kv-size 32768 --max-tokens 2048
```

### Was die Optionen bedeuten

```text
--max-kv-size 32768
```

begrenzt den KV-Cache auf 32K Einträge. `mlx-lm` verwendet bei Modellen ohne eigene `make_cache`-Implementierung dafür einen rotierenden KV-Cache.

```text
--max-tokens 2048
```

begrenzt nur die **maximale Länge einer einzelnen Antwort**.

Das ist wichtig:

**`max-kv-size` ≠ `max-tokens`.**

---

# 3. Qwen testen

Gib zum Beispiel ein:

```text
Write a Python function that computes the eigenvalues of a 2x2 real matrix. Explain numerical stability and edge cases.
```

Danach:

```text
Review this function for bugs, edge cases and performance problems. Give me a corrected implementation.
```

Wenn alles funktioniert:

**`Ctrl+C`** zum Beenden.

---

# 4. Qwen für deinen Alltag

Ich würde Qwen3.8-9B zunächst mit diesen Werten betreiben:

| Einstellung | Wert |
|---|---:|
| Quantisierung | 4-bit |
| KV-Cache | **32K** |
| Antwort | **2048 Tokens** |
| Aufgabe | normales Coding |

32K ist für Qwen auf deinem 24-GB-Air ein sinnvoller Startpunkt, weil das Modell selbst nur rund 5 GB belegt.

Wenn du später siehst, dass 32K unnötig viel ist, kannst du auf 16K reduzieren.

---

# 5. Modell 2: Devstral Small 2 24B

Für schwierigere Aufgaben verwenden wir:

```text
mlx-community/Devstral-Small-2-24B-Instruct-2512-OptiQ-4bit
```

Das ist keine einfache uniforme 4-bit-Quantisierung. OptiQ verteilt mehr Bits auf empfindliche Layer; die Modellkarte nennt **5,01 bits/weight** und etwa **15,4 GB** Modellgröße. In der veröffentlichten Vergleichsmessung schlägt es die dort verwendete uniforme 4-bit-Variante beim Capability Score und besonders beim Long-Context-Retrieval.

## Erst einmal ohne Agenten testen

```bash
uv run mlx_lm.chat --model "mlx-community/Devstral-Small-2-24B-Instruct-2512-OptiQ-4bit" --max-kv-size 16384 --max-tokens 2048
```

### Warum nur 16K KV-Cache?

Devstral benötigt bereits ungefähr 15,4 GB für die Gewichte. Auf deinem 24-GB-Air müssen zusätzlich macOS, MLX, IDE und KV-Cache hineinpassen.

Daher:

```text
Qwen 9B       → 32K KV
Devstral 24B  → 16K KV
```

Das ist absichtlich **modelspezifisch**.

Wenn Devstral bei 16K völlig problemlos läuft, können wir später 24K und 32K testen.

---

# 6. Speicher beobachten

Während das Modell läuft:

**Aktivitätsanzeige → Speicher**

Entscheidend sind:

### Speicherdruck

```text
GRÜN   → gut
GELB   → grenzwertig
ROT    → zu aggressiv
```

### Swap

Für deinen Air wollen wir möglichst wenig Swap.

Besonders Devstral solltest du einige Minuten unter Last laufen lassen. Der Air hat keinen Lüfter; nachhaltige Leistung ist wichtiger als ein kurzer Peak.

---

# 7. Bequeme Startskripte

Damit du nicht jedes Mal die langen Befehle eintippen musst:

```bash
mkdir -p ~/local-llm/scripts
```

## Qwen

```bash
printf '%s\n' '#!/bin/zsh' 'cd ~/local-llm' 'uv run mlx_lm.chat --model "keXjos/Qwen3.8-9B-mlx-4Bit" --max-kv-size 32768 --max-tokens 2048' > ~/local-llm/scripts/qwen.sh
```

## Devstral

```bash
printf '%s\n' '#!/bin/zsh' 'cd ~/local-llm' 'uv run mlx_lm.chat --model "mlx-community/Devstral-Small-2-24B-Instruct-2512-OptiQ-4bit" --max-kv-size 16384 --max-tokens 2048' > ~/local-llm/scripts/devstral.sh
```

Ausführbar machen:

```bash
chmod +x ~/local-llm/scripts/qwen.sh ~/local-llm/scripts/devstral.sh
```

Jetzt reicht:

```bash
~/local-llm/scripts/qwen.sh
```

oder:

```bash
~/local-llm/scripts/devstral.sh
```

---

# 8. Für VS Code: lokaler API-Server

Wenn du das Modell aus VS Code heraus verwenden willst, brauchst du einen Server statt `mlx_lm.chat`.

## Qwen starten

```bash
uv run mlx_lm.server --model "keXjos/Qwen3.8-9B-mlx-4Bit" --host 127.0.0.1 --port 8080
```

Das Terminal bleibt offen.

In einem zweiten Terminal testen:

```bash
curl http://127.0.0.1:8080/v1/models
```

Wenn JSON zurückkommt, läuft der Server.

`mlx-lm` stellt eine OpenAI-kompatible API bereit.

### Wichtiger Unterschied beim KV-Cache

Bei `mlx_lm.chat` kannst du in deiner aktuellen Version explizit:

```text
--max-kv-size
```

setzen. Dein `--help` hat das bestätigt.

Beim **Server** solltest du dagegen nicht einfach irgendwelche alten Blog-Parameter wie `--num-ctx` oder `--max-context-length` übernehmen. Die Server-CLI ist versionsabhängig.

Prüfe deshalb deine konkrete Version mit:

```bash
uv run mlx_lm.server --help
```

Wir konfigurieren dort nur Optionen, die deine installierte Version tatsächlich unterstützt.

---

# 9. VS Code installieren

Installiere in VS Code die Extension:

```text
Continue
```

Dann verbindest du Continue mit deinem lokalen OpenAI-kompatiblen Server.

Grunddaten:

```text
Provider:
OpenAI-compatible

Base URL:
http://127.0.0.1:8080/v1

Model:
keXjos/Qwen3.8-9B-mlx-4Bit
```

Damit ist dein Aufbau:

```text
VS Code
   ↓
Continue
   ↓
localhost:8080
   ↓
MLX-LM
   ↓
Qwen3.8-9B
```

---

# 10. Jetzt tatsächlich lokal programmieren

Öffne ein Projekt:

```bash
cd ~/mein-projekt
code .
```

In Continue beispielsweise:

```text
Analyze this repository without modifying anything.

Explain:
1. the project structure,
2. the main entry points,
3. the test setup,
4. the most important modules.
```

Danach kannst du kleinere Aufgaben direkt lokal erledigen:

```text
Find the bug in this function and propose a minimal fix.
```

```text
Write unit tests for this class.
```

```text
Refactor this function without changing its public API.
```

---

# 11. Devstral für schwierige Aufgaben

Wenn Qwen bei einer Aufgabe schwächelt, beenden wir den Qwen-Server mit:

```text
Ctrl+C
```

und starten Devstral:

```bash
uv run mlx_lm.server --model "mlx-community/Devstral-Small-2-24B-Instruct-2512-OptiQ-4bit" --host 127.0.0.1 --port 8080
```

In Continue ändert sich nur das Modell auf:

```text
mlx-community/Devstral-Small-2-24B-Instruct-2512-OptiQ-4bit
```

Devstral Small 2 ist speziell für Software Engineering, Codebase Exploration, Multi-File Editing und Tool Use ausgelegt.

---

# 12. Agentic Coding mit Devstral

Für einfache Chat-/Edit-Aufgaben reicht `mlx-lm`.

Für **mehrstufiges Tool Calling** ist die OptiQ-Version interessanter, weil deren Modellkarte ausdrücklich `mlx-optiq` als Server für Multi-Step-Tool-Use nennt. Dieser Server bietet OpenAI- und Anthropic-kompatible Schnittstellen.

Installieren:

```bash
uv add mlx-optiq
```

Dann:

```bash
uv run optiq serve --model "mlx-community/Devstral-Small-2-24B-Instruct-2512-OptiQ-4bit" --host 127.0.0.1 --port 8080
```

Falls deine installierte Version andere Optionen verlangt:

```bash
uv run optiq serve --help
```

---

# 13. Claude Code

Hier ist die Architektur:

```text
Claude Code
     ↓
Anthropic-kompatible API
     ↓
mlx-optiq
     ↓
Devstral Small 2
```

Claude Code kann über `ANTHROPIC_BASE_URL` an einen alternativen API-Endpunkt geroutet werden. Die aktuelle Anthropic-Dokumentation beschreibt diese Variable ausdrücklich für Proxies/Gateways und erlaubt außerdem ein eigenes Modell über `ANTHROPIC_CUSTOM_MODEL_OPTION`.

Für einen lokalen Server setzt du beispielsweise:

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8080"
```

und startest anschließend Claude Code.

**Hier würde ich nicht einfach behaupten, dass jede beliebige `mlx-lm`-Serverversion direkt mit Claude Code funktioniert.** Entscheidend ist, dass der verwendete Server tatsächlich die von Claude Code erwartete Anthropic-Messages-API bereitstellt. Genau deshalb verwenden wir für Devstral-Agenten `mlx-optiq` und nicht blind den normalen `mlx_lm.server`. Die Devstral-Modellkarte nennt dessen Anthropic-Kompatibilität ausdrücklich.

---

# 14. Git vor dem Agenten

Bevor du einem Agenten Schreib- und Terminalrechte gibst:

```bash
git status
```

Idealerweise vorher:

```bash
git add . && git commit -m "before local AI changes"
```

Danach kannst du jederzeit prüfen:

```bash
git diff
```

Ein Agent darf Änderungen vorschlagen und durchführen; **die Software muss aber prüfen, ob Tool-Aufrufe tatsächlich erfolgreich waren**.

---

# 15. Welche Aufgabe bekommt welches Modell?

## Qwen3.8-9B

**Daily Driver**

- einzelne Funktionen
- Erklärungen
- kleine Bugs
- Tests
- Refactoring
- Boilerplate
- schnelle Fragen

**Einstellung:**

```text
4-bit
32K KV
2048 max output
```

## Devstral Small 2 24B

**Heavy Mode**

- komplexe Bugs
- größere Refactorings
- mehrere Dateien
- Repository-Analyse
- Tool Calling
- Agentic Coding

**Einstellung:**

```text
OptiQ 4-bit
16K KV
2048 max output
```

---

# 16. Unsere Testphase

Bevor du dich endgültig festlegst, testen wir beide Modelle mit denselben Aufgaben:

### Test A – einfache Implementierung

```text
Implement this function and write unit tests.
```

### Test B – Debugging

Absichtlich fehlerhaften Code analysieren.

### Test C – Refactoring

Eine größere Datei verbessern, ohne die API zu verändern.

### Test D – Multi-File

Mehrere Dateien zusammen verstehen und verändern.

### Test E – Agent

```text
Inspect the repository, identify the bug, implement the fix,
run the tests, and fix any resulting failures.
```

Wir vergleichen dabei:

```text
Generation tok/s
RAM
Memory Pressure
Swap
Zeit bis zur Lösung
Anzahl Fehlversuche
Codequalität
Test-Erfolg
Tool-Call-Erfolg
```

Das ist für deinen Rechner wesentlich aussagekräftiger als Benchmarks von einem M5 Max oder Desktop.

---

# 17. Meine Startkonfiguration

| | Qwen3.8-9B | Devstral Small 2 |
|---|---:|---:|
| Quantisierung | 4-bit | OptiQ 4-bit |
| Modellgröße | ~5,0 GB | ~15,4 GB |
| KV-Cache | **32K** | **16K** |
| Max. Antwort | 2048 | 2048 |
| Einsatz | Daily Driver | Heavy Mode |
| API | `mlx_lm.server` | `mlx-optiq` für Agenten |
| Ziel | VS Code/Continue | Claude Code/Agent |

Die Qwen-MLX-Datei ist aktuell etwa 5,04 GB groß; die Devstral-OptiQ-Version liegt bei etwa 15,4 GB.

---

# 18. Die vier wichtigsten Befehle

### Qwen-Chat

```bash
uv run mlx_lm.chat --model "keXjos/Qwen3.8-9B-mlx-4Bit" --max-kv-size 32768 --max-tokens 2048
```

### Devstral-Chat

```bash
uv run mlx_lm.chat --model "mlx-community/Devstral-Small-2-24B-Instruct-2512-OptiQ-4bit" --max-kv-size 16384 --max-tokens 2048
```

### Qwen-Server für VS Code

```bash
uv run mlx_lm.server --model "keXjos/Qwen3.8-9B-mlx-4Bit" --host 127.0.0.1 --port 8080
```

### Devstral-Agent-Server

```bash
uv run optiq serve --model "mlx-community/Devstral-Small-2-24B-Instruct-2512-OptiQ-4bit" --host 127.0.0.1 --port 8080
```

**Keine Backslashes nötig. Alles in eine Zeile kopieren.**

---

# 19. Was wir bewusst nicht tun

Wir setzen nicht einfach:

```text
256K Kontext
```

nur weil das Modell ihn unterstützt.

Wir nehmen nicht automatisch die größtmögliche Quantisierung.

Wir lassen nicht beide großen Modelle gleichzeitig im Speicher.

Und wir geben einem Agenten nicht blind Schreibrechte, ohne Git und Tool-Erfolgskontrolle.

Das Ziel ist nicht, das Modell gerade noch in 24 GB hineinzuzwingen. Das Ziel ist, dass dein **lüfterloser M5 Air dauerhaft angenehm und zuverlässig damit arbeitet**.