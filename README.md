# Video Censor — Docker

## Build (on host machine)

```bash
cd /home/jenn/tkc/censor/docker
./build.sh       # copies app scripts locally
docker compose build
```

## Deploy to TrueNAS

**Option A — push image to registry:**
```bash
docker tag censor_censor your-registry/video-censor
docker push your-registry/video-censor
```
Then on TrueNAS: pull the image, map port 8501.

**Option B — copy docker/ dir to NAS:**
```bash
cp -r /home/jenn/tkc/censor/docker /some/nas/share/
```
On TrueNAS: `cd /mnt/pool/docker && docker compose build && docker compose up -d`

Only the `docker/` directory needs to go (~10KB + downloaded layers). No massive `censor_env/`.

## Usage

Open `http://<nas-ip>:8501`. Default is app3.py (interactive with bleep padding, audio preview, manual timestamps).