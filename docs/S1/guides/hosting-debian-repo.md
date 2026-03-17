# Hosting a Custom Debian Package Repository

**Date researched:** 2026-03-17
**Target OS:** Debian 13 Trixie (armhf)
**Purpose:** Host custom FLSUN OS packages (kernel, Klipper, system configs) for `apt` delivery

---

## 1. Overview

A Debian package repository is a directory structure that APT can fetch packages from via HTTP(S). Two approaches exist:

| Approach | Tool | Complexity | Best For |
|---|---|---|---|
| **Flat repository** | Manual (dpkg-scanpackages) | Low | < 10 packages, quick testing |
| **Full repository** | `reprepro` | Medium | Production, multiple distributions, signed |
| **GitHub Pages** | `reprepro` + static hosting | Low ops | Open-source projects, no server needed |

This guide covers `reprepro` — it handles GPG signing, multiple architectures, component management, and is the standard for small-to-medium Debian repos.

---

## 2. Server Setup (Debian 13)

### 2.1 Install Required Packages

```bash
sudo apt update
sudo apt install reprepro gnupg nginx
```

### 2.2 Create GPG Signing Key

APT repositories must be GPG-signed so clients can verify package authenticity.

```bash
# Generate a signing key (no passphrase for automated builds, or use gpg-agent)
gpg --batch --gen-key <<EOF
%no-protection
Key-Type: RSA
Key-Length: 4096
Subkey-Type: RSA
Subkey-Length: 4096
Name-Real: FLSUN OS Package Signing
Name-Email: packages@flsun-os.example.com
Expire-Date: 5y
%commit
EOF

# Note the key ID
gpg --list-keys --keyid-format long packages@flsun-os.example.com
# Example output: rsa4096/ABCDEF1234567890

# Export the public key (clients need this)
gpg --armor --export packages@flsun-os.example.com \
    > flsun-os-archive-keyring.gpg
```

### 2.3 Create Repository Structure

```bash
REPO_DIR="/srv/reprepro/flsun-os"
sudo mkdir -p "${REPO_DIR}/conf"
```

Create `${REPO_DIR}/conf/distributions`:

```
Origin: FLSUN-OS
Label: FLSUN OS Custom Packages
Codename: trixie
Architectures: armhf
Components: main
Description: Custom packages for FLSUN OS (S1/T1 3D printers)
SignWith: ABCDEF1234567890
```

Replace `ABCDEF1234567890` with your actual GPG key ID.

Create `${REPO_DIR}/conf/options`:

```
verbose
basedir /srv/reprepro/flsun-os
ask-passphrase
```

### 2.4 Initialize the Repository

```bash
cd "${REPO_DIR}"
reprepro export
```

This creates the `dists/` and `pool/` directories.

---

## 3. Adding Packages

### 3.1 Add a .deb to the Repository

```bash
cd /srv/reprepro/flsun-os

# Add a kernel package
reprepro includedeb trixie /path/to/flsun-os-kernel-s1_6.1.115-1_armhf.deb

# Add another package
reprepro includedeb trixie /path/to/flsun-os-base_1.0-1_armhf.deb
```

### 3.2 List Packages

```bash
reprepro list trixie
```

### 3.3 Remove a Package

```bash
reprepro remove trixie flsun-os-kernel-s1
```

### 3.4 Replace a Package (new version)

```bash
# reprepro automatically replaces when a newer version is added
reprepro includedeb trixie /path/to/flsun-os-kernel-s1_6.1.115-2_armhf.deb
```

---

## 4. Serving via Nginx

### 4.1 Nginx Configuration

Create `/etc/nginx/sites-available/packages`:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name packages.flsun-os.example.com;

    root /srv/reprepro/flsun-os;

    # Serve the repository
    location / {
        autoindex on;
        autoindex_exact_size off;
        autoindex_localtime on;
    }

    # Cache control for package metadata — clients should revalidate
    location /dists/ {
        add_header Cache-Control "no-cache";
    }

    # Package files are immutable (version in filename)
    location /pool/ {
        add_header Cache-Control "max-age=2592000";  # 30 days
    }
}
```

Enable and reload:

```bash
sudo ln -s /etc/nginx/sites-available/packages /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 4.2 HTTPS with Let's Encrypt (Production)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d packages.flsun-os.example.com
```

---

## 5. Client Setup (on the FLSUN Printer)

### 5.1 Add the Repository Keyring

Copy the GPG public key to the printer:

```bash
# On the build machine
scp flsun-os-archive-keyring.gpg pi@printer:/tmp/

# On the printer
sudo mkdir -p /usr/share/keyrings
sudo cp /tmp/flsun-os-archive-keyring.gpg /usr/share/keyrings/
```

### 5.2 Add the APT Source

```bash
echo "deb [signed-by=/usr/share/keyrings/flsun-os-archive-keyring.gpg] \
https://packages.flsun-os.example.com/debian trixie main" \
| sudo tee /etc/apt/sources.list.d/flsun-os.list
```

### 5.3 Add APT Pinning

Create `/etc/apt/preferences.d/flsun-os.pref`:

```
# Prefer FLSUN OS repo for all flsun-* packages
Package: flsun-*
Pin: origin packages.flsun-os.example.com
Pin-Priority: 900

# Prevent base-files from overwriting custom hostname/fstab
Package: base-files
Pin: release o=Debian
Pin-Priority: 100
```

### 5.4 Test

```bash
sudo apt update
apt list --upgradable
sudo apt install flsun-os-kernel-s1
```

---

## 6. Alternative: GitHub Pages / Static Hosting

For open-source projects, the repository can be hosted as static files on GitHub Pages, Cloudflare Pages, or any static file host. No server-side processing is needed — APT just fetches files over HTTP.

### 6.1 Repository Layout for Static Hosting

```
repo/
├── dists/
│   └── trixie/
│       ├── InRelease          # Signed package index (GPG clearsigned)
│       ├── Release            # Package checksums
│       ├── Release.gpg        # Detached GPG signature
│       └── main/
│           └── binary-armhf/
│               ├── Packages       # Package metadata
│               ├── Packages.gz    # Compressed metadata
│               └── Release        # Component metadata
└── pool/
    └── main/
        └── f/
            └── flsun-os-kernel-s1/
                └── flsun-os-kernel-s1_6.1.115-1_armhf.deb
```

### 6.2 Build with reprepro, Deploy as Static

```bash
# Build locally
cd /srv/reprepro/flsun-os
reprepro includedeb trixie *.deb

# Deploy to GitHub Pages (or any static host)
# Copy the entire /srv/reprepro/flsun-os/ to the static hosting root
rsync -av /srv/reprepro/flsun-os/ gh-pages-checkout/
cd gh-pages-checkout && git add . && git commit -m "Update packages" && git push
```

### 6.3 Client APT Source for GitHub Pages

```
deb [signed-by=/usr/share/keyrings/flsun-os-archive-keyring.gpg] \
    https://your-org.github.io/flsun-os-repo trixie main
```

---

## 7. Alternative: Flat Repository (Quick Testing)

For quick testing with a handful of packages, no reprepro needed:

### 7.1 Create the Flat Repo

```bash
REPO_DIR="/srv/packages"
mkdir -p "${REPO_DIR}"

# Copy .deb files
cp build/output/flsun-os-kernel-s1_*.deb "${REPO_DIR}/"

# Generate package index
cd "${REPO_DIR}"
dpkg-scanpackages --multiversion . /dev/null | gzip -9c > Packages.gz
dpkg-scanpackages --multiversion . /dev/null > Packages
```

### 7.2 Serve via Nginx

Same as section 4, but point root to `/srv/packages`.

### 7.3 Client APT Source (Flat Format)

Note the `./` — this tells APT it's a flat repository:

```
deb [trusted=yes] http://your-server/packages ./
```

The `[trusted=yes]` skips GPG verification — only use for local testing.

---

## 8. CI/CD Integration (GitHub Actions)

Automate package publishing on tagged releases:

```yaml
# .github/workflows/publish-packages.yml
name: Build and Publish Packages

on:
  push:
    tags: ['v*']

jobs:
  build-kernel-deb:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true

      - name: Install cross-compiler
        run: |
          sudo apt-get update
          sudo apt-get install -y gcc-arm-linux-gnueabihf bc flex bison libssl-dev

      - name: Build kernel
        run: |
          cd build
          chmod +x build-kernel.sh
          ./build-kernel.sh --target s1

      - name: Package kernel .deb
        run: |
          cd build
          chmod +x package-kernel-deb.sh
          ./package-kernel-deb.sh --target s1 --version ${GITHUB_REF_NAME#v}

      - name: Upload .deb artifact
        uses: actions/upload-artifact@v4
        with:
          name: kernel-deb
          path: build/output/*.deb

  publish:
    needs: build-kernel-deb
    runs-on: ubuntu-latest
    steps:
      - name: Download artifacts
        uses: actions/download-artifact@v4

      - name: Import GPG key
        run: echo "${{ secrets.GPG_PRIVATE_KEY }}" | gpg --batch --import

      - name: Add to repository
        run: |
          sudo apt-get install -y reprepro
          reprepro -b repo/ includedeb trixie kernel-deb/*.deb

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./repo
```

---

## 9. Repository Directory Reference

After setup, the complete repository structure on the server:

```
/srv/reprepro/flsun-os/
├── conf/
│   ├── distributions          # Release definition (codename, arch, GPG key)
│   └── options                # reprepro options
├── db/                        # reprepro internal database (auto-generated)
├── dists/
│   └── trixie/
│       ├── InRelease          # Signed metadata (APT fetches this first)
│       ├── Release
│       ├── Release.gpg
│       └── main/
│           └── binary-armhf/
│               ├── Packages
│               ├── Packages.gz
│               └── Release
└── pool/
    └── main/
        └── f/
            ├── flsun-os-kernel-s1/
            │   └── flsun-os-kernel-s1_6.1.115-1_armhf.deb
            ├── flsun-os-base/
            │   └── flsun-os-base_1.0-1_armhf.deb
            └── flsun-klipper/
                └── flsun-klipper_1.0-1_armhf.deb
```

---

## 10. Security Considerations

1. **Always use HTTPS** — APT over HTTP is vulnerable to man-in-the-middle (package substitution).
2. **Always sign the repository** — `SignWith` in reprepro distributions config. Never use `[trusted=yes]` in production.
3. **Protect the GPG private key** — store in CI secrets or a hardware token, never in the repository.
4. **Pin packages** — APT pinning prevents Debian's repos from overriding FLSUN packages even if Debian ships a similarly-named package in the future.
5. **postinst script safety** — the kernel postinst writes to a raw block device (`dd`). It must validate the boot.img magic (`ANDROID!`) before writing and refuse to write to non-FLSUN hardware.
