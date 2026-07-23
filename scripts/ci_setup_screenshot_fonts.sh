#!/usr/bin/env bash
# Install CJK/Latin fonts and fontconfig aliases so LibreOffice headless
# PPTX→PDF substitutes Microsoft YaHei / Arial (used by PptxGen theme).
# Without this, Linux CI screenshots render Chinese as tofu (□).
set -euo pipefail

sudo apt-get update
sudo apt-get install -y fonts-noto-cjk fonts-liberation fontconfig

sudo tee /etc/fonts/conf.d/99-archium-cjk-aliases.conf >/dev/null <<'EOF'
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <alias binding="same">
    <family>Microsoft YaHei</family>
    <prefer>
      <family>Noto Sans CJK SC</family>
      <family>Noto Sans CJK</family>
    </prefer>
  </alias>
  <alias binding="same">
    <family>微软雅黑</family>
    <prefer>
      <family>Noto Sans CJK SC</family>
      <family>Noto Sans CJK</family>
    </prefer>
  </alias>
  <alias binding="same">
    <family>Arial</family>
    <prefer>
      <family>Liberation Sans</family>
    </prefer>
  </alias>
</fontconfig>
EOF

sudo fc-cache -f
yahei_match="$(fc-match 'Microsoft YaHei')"
arial_match="$(fc-match Arial)"
echo "fc-match Microsoft YaHei => ${yahei_match}"
echo "fc-match Arial => ${arial_match}"
# Fail fast: LibreOffice will draw □ for CJK if YaHei does not resolve to Noto.
if ! grep -qiE 'Noto|CJK|WenQuanYi|Source Han' <<<"${yahei_match}"; then
  echo "ERROR: Microsoft YaHei did not resolve to a CJK font (${yahei_match})" >&2
  exit 1
fi
