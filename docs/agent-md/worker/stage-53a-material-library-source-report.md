# Stage53-A Material Library Source Report

Generated at: 2026-06-03T02:40:47+08:00

## Scope Boundary

- Allowed write paths used: `shared_data/material_library/**` and this report.
- Backend, frontend, and tests were not modified.
- No UVR, RVC, or training workflow was run.
- Stage download policy: only traceable Public Domain, CC0, or CC-BY sources; target single file under 20 MB; total under 100 MB.
- This pre-download report records the source URL, license basis, intended use, and save path before any network file download.

## Planned Downloads Before Network Fetch

| ID | Source URL | License basis | Intended use | Save path | Preflight |
| --- | --- | --- | --- | --- | --- |
| `commons_jimmy_wales_voice_cc0_001` | https://commons.wikimedia.org/wiki/File:Jimmy_Wales_voice.ogg | CC0 1.0 per Wikimedia Commons file page | Small voice-only demo for path/import smoke tests; not singing quality material | `shared_data/material_library/authorized_dry_vocals/public_domain_voice/jimmy_wales_voice_cc0.ogg` | HEAD 200, 108035 bytes |
| `librivox_abou_hunt_public_domain_001` | https://librivox.org/short-poetry-collection-001/ | Public Domain per LibriVox recording policy: https://librivox.org/pages/public-domain/ | Small public-domain spoken voice demo for non-training smoke tests | `shared_data/material_library/authorized_dry_vocals/public_domain_voice/librivox_abou_hunt_py_public_domain.mp3` | HEAD 200, 1745024 bytes |
| `commons_acoustic_guitar_public_domain_001` | https://commons.wikimedia.org/wiki/File:AcousticGuitarSample.ogg | Public Domain per Wikimedia Commons file page | Small instrument-only separation/waveform handling reference | `shared_data/material_library/separation_benchmarks/public_domain/acoustic_guitar_sample_public_domain.ogg` | HEAD 200, 889069 bytes |

## Local User-Provided Material Manifested Only

| ID | External path | Size | Manifest action | Rights judgment |
| --- | --- | ---: | --- | --- |
| `user_zhu_zhu_dry_voice_001` | `C:\Users\ASUS\Desktop\干声文件\朱朱干声.mp3` | 37309203 bytes | Backed up to `shared_data/material_library/authorized_dry_vocals/user/朱朱干声.mp3` after user requested local consolidation | User-provided local material; no redistribution/export/publishing rights asserted by Stage53-A |
| `user_zhu_zhu_dry_voice_singing_002` | `C:\Users\ASUS\Desktop\干声文件\朱朱干声唱.mp3` | 108400926 bytes | Backed up to `shared_data/material_library/authorized_dry_vocals/user/朱朱干声唱.mp3` after user requested local consolidation | User-provided local material; no redistribution/export/publishing rights asserted by Stage53-A |

## Not Downloaded

| Candidate | Reason |
| --- | --- |
| Commons `Dial_up_connection_(short).oga` redirect | HEAD preflight returned HTTP 429; source/license page was not revalidated in this run, so it was not downloaded. |
| Old public-domain commercial-song recordings | Avoided even where public-domain candidates may exist, because this stage explicitly forbids commercial songs. |
| Large open datasets | Avoided to keep total size low and because this stage forbids UVR/RVC/training. |
| Unknown-license web uploads | Not downloaded; uncertain sources belong in `quarantine/` or manual review only. |

## Downloaded / Generated Material

| ID | Project path | Status | Size | SHA256 |
| --- | --- | --- | ---: | --- |
| `commons_jimmy_wales_voice_cc0_001` | `shared_data/material_library/authorized_dry_vocals/public_domain_voice/jimmy_wales_voice_cc0.ogg` | Downloaded and hash-verified | 108035 bytes | `A5A1F939CF0514BEC3709DB1E4B6CB36C60A17AE359394A81D92EE5F3CA65087` |
| `librivox_abou_hunt_public_domain_001` | `shared_data/material_library/authorized_dry_vocals/public_domain_voice/librivox_abou_hunt_py_public_domain.mp3` | Downloaded and hash-verified | 1745024 bytes | `47ACBA9234416F0533064EFFF7DE9537950DC13C927DC0B3F5BDDEC297CE6068` |
| `commons_acoustic_guitar_public_domain_001` | `shared_data/material_library/separation_benchmarks/public_domain/acoustic_guitar_sample_public_domain.ogg` | Downloaded and hash-verified | 889069 bytes | `1C604CCE5299B2F9579538810DEB328D9C47607F098F5885FF1DAA7CF34B637A` |
| `synthetic_vowel_tone_mix_8s_001` | `shared_data/material_library/separation_benchmarks/synthetic/synthetic_vowel_tone_mix_8s.wav` | Generated synthetic, hash-verified | 256044 bytes | `C2E0FB527CB27A9BEF38C41E1C5859B7BBA1CB02CCB5FD65D9F6CB04BCC2C288` |

Total downloaded/generated project material size: 2998172 bytes.

## Copyright Judgment

- `Jimmy_Wales_voice.ogg`: accepted for Stage53-A because the traceable Wikimedia Commons file page states CC0 1.0. Risk is low for internal smoke testing; it is speech, not singing.
- `librivox_abou_hunt_py_public_domain.mp3`: accepted for Stage53-A because LibriVox states recordings are public domain and the collection page is traceable. Risk is low for internal smoke testing; it is speech, not singing.
- `acoustic_guitar_sample_public_domain.ogg`: accepted for Stage53-A because the traceable Wikimedia Commons file page states Public Domain. Risk is low for internal waveform/separation smoke testing; it is instrument-only.
- `synthetic_vowel_tone_mix_8s.wav`: accepted as generated internal synthetic signal with no third-party source audio. It is not a real vocal, music, or quality benchmark.
- User-provided local Zhu Zhu dry vocal files were later copied into `shared_data/material_library/authorized_dry_vocals/user` at the user's request to prevent accidental desktop deletion. They remain manual-confirmation material for any training/export/publishing use.

## Risk Summary

- No commercial songs, DJ versions, competitor materials, unknown-license songs, or large datasets were downloaded.
- No copied project material exceeds 20 MB; total copied/generated project material is under 100 MB.
- The local Zhu Zhu files include one file over 100 MB. They were copied only after explicit user request for local consolidation and remain under ignored `shared_data/`.
- Correction after architect review: public-domain/CC0 voice demo placeholders were moved out of `sonovox_demo` into `authorized_dry_vocals/public_domain_voice`. The `sonovox_demo` folder is reserved for the real user-provided Sonovox dataset only.
