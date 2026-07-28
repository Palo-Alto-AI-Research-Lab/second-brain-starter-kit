---
name: tt-probe
description: E2E-проба конвейера fleet-skill-autonomy (создан на MAC-1 2026-07-16 для verify #41ac669a). Не вызывать - это тестовый маркер, после верификации писатель может удалить.
permissions: [filesystem]
risk_level: inert
processes_untrusted_data: false
disable-model-invocation: true
origin: MAC-1
---

# tt-probe — маркер end-to-end промоушена

Единственная задача файла: пройти путь local-скилл → гейт → писатель (Якорь) → общий набор → синк на все машины.
Если ты читаешь это в `skills/tt-probe/` на любой машине флота — конвейер автономии скиллов РАБОТАЕТ.
Проба: PROBE-41ac669a-20260716.
