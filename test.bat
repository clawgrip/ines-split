@echo off
choice /c NY /m "This batch file will DELETE some files. Continue"
if not errorlevel 2 goto end

if not exist test-in\*.* goto end
if not exist test-out\*.* goto end

cls
if exist test-out\*.prg del test-out\*.prg
if exist test-out\*.chr del test-out\*.chr
if exist test-out\*.trn del test-out\*.trn

echo Converting files under "test-in" to files under "test-out"...
cd test-in
for %%f in (*.*) do python ..\ines_split.py -p "..\test-out\%%f.prg" -c "..\test-out\%%f.chr" -t "..\test-out\%%f.trn" "%%f"
cd ..

:end
