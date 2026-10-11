# Which MoeGUI is which

Updated 2026-09-09. The previous version of this file said the J: copy "is
under git" and was "the live tree". Both halves were wrong, and the file had
been mirrored into *both* copies by the vault sync, so it sat in each one
telling the reader that the other was authoritative.

## The three locations, measured

| path | role | git |
|---|---|---|
| `C:\Users\viper\gan-otg-db\MoeGUI` | **the build tree** — `mvn package` runs here | **yes, this repo** |
| `C:\Viper\projects\MoeGUI` | junction to the line above; same files | same repo |
| `J:\ViperVault\code\projects\MoeGUI` | vault mirror + the **deploy** location | no |

`supervisor.py` launches the app from
`J:\ViperVault\code\projects\MoeGUI\run\MoeGUI-1.0.0.jar`, so **a rebuild alone
changes nothing** — the JAR has to be copied to `run\` for the running app to
pick it up. Verify by sha256 on both ends and by reading the live process
command line, never by trusting the build output.

## Divergence found on 2026-09-09

`PythonBridge.java` was 9513 bytes here and 4884 bytes on J:. The deployed JAR
was built from *this* tree, so the running app had the bridge self-heal fix
while the J: source still held the version without it. A mirror that receives
files by robocopy has no way to notice it is behind.

That is the reason this tree is now the one under version control: the copy that
gets built is the copy whose history matters.

## What is not committed

`target/` (114 MB of shaded JARs) and `run/*.jar` (29 MB). Both are build
artifacts that regenerate from this source, and a 29 MB blob per rebuild would
make the repo unusable inside a week. Binaries ship via `release_binaries.ps1`.
