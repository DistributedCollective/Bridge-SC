#!/usr/bin/env bash
# Upgrade only the existing ETH federator. Parameters are arguments or terminal prompts.
set +x
set -Eeuo pipefail
unset PYTHONOPTIMIZE PYTHONINSPECT
umask 077
VERSION=1.3.0
FED_REPO="$HOME/Bridge-SC"
REPO_OVERRIDE=''
REPAIR_REVISION=''
APP_REVISION=''
FED_IMAGE=''
RELEASE_OVERRIDE=''
PUBLIC_OPERATOR=''
EXPECTED_SIGNER=''
KEY_SOURCE=aws
KEY_SOURCE_OVERRIDE=false
WATCH_OVERRIDE=''
WATCH_SECONDS=900
ROLLBACK_RUN=''
OPS_DIR=''
STAGE=arguments
SCRIPT_FILE=${BASH_SOURCE[0]}
usage() {
  cat <<'HELP'
Usage: bash upgrade-eth-federator.sh [options]
Missing release/public inputs are requested interactively. Never edit this file.
  --repo PATH                 Existing Bridge-SC checkout (default ~/Bridge-SC)
  --revision FULL_COMMIT      Approved upgrade-tool revision
  --app-revision FULL_COMMIT  Image source revision (defaults to --revision)
  --image TAG@sha256:DIGEST   Approved sovryn/fed-tokenbridge image
  --override PATH             Supplied private Compose override
  --operator fed_1..fed_5     Anonymous node label
  --expected-signer ADDRESS  This node's approved public federator address
  --no-aws-secrets            Restore original key manually instead of AWS
  --watch-seconds SECONDS    Post-upgrade watcher duration, 1..86400 (default 900)
  --rollback RUN_DIRECTORY   Restore an archived image, then verify key and start
  --help | --version
HELP
}
parameter_error() { printf '%s\n' "$1" >&2; exit 2; }
while (($#)); do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --version) printf 'federator-upgrade %s\n' "$VERSION"; exit 0 ;;
    --no-aws-secrets) KEY_SOURCE=manual; KEY_SOURCE_OVERRIDE=true; shift ;;
    --repo|--revision|--app-revision|--image|--override|--operator|--expected-signer|--watch-seconds|--rollback)
      (($#>=2)) && [[ "$2" != --* && -n "$2" ]] || parameter_error "Missing value for $1"
      case "$1" in
        --repo) FED_REPO=$2; REPO_OVERRIDE=$2 ;; --revision) REPAIR_REVISION=$2 ;;
        --app-revision) APP_REVISION=$2 ;; --image) FED_IMAGE=$2 ;; --override) RELEASE_OVERRIDE=$2 ;;
        --operator) PUBLIC_OPERATOR=$2 ;; --expected-signer) EXPECTED_SIGNER=$2 ;;
        --watch-seconds) WATCH_SECONDS=$2; WATCH_OVERRIDE=$2 ;; --rollback) ROLLBACK_RUN=$2 ;;
      esac
      shift 2 ;;
    *) parameter_error 'Unknown parameter; use --help' ;;
  esac
done
[[ "$WATCH_SECONDS" =~ ^[0-9]{1,5}$ ]] || parameter_error 'Invalid watcher duration'
((10#$WATCH_SECONDS>=1 && 10#$WATCH_SECONDS<=86400)) || parameter_error 'Watcher duration must be 1..86400'
[[ -z "$PUBLIC_OPERATOR" || "$PUBLIC_OPERATOR" =~ ^fed_[1-5]$ ]] || parameter_error 'Invalid fed_n label'
[[ -z "$REPAIR_REVISION" || "$REPAIR_REVISION" =~ ^[0-9a-f]{40}$ ]] || parameter_error 'Revision must be a full lowercase commit ID'
[[ -z "$APP_REVISION" || "$APP_REVISION" =~ ^[0-9a-f]{40}$ ]] || parameter_error 'Application revision must be a full lowercase commit ID'
[[ -z "$EXPECTED_SIGNER" || "$EXPECTED_SIGNER" =~ ^0x[0-9a-fA-F]{40}$ ]] || parameter_error 'Expected signer must be a public address'
[[ -z "$FED_IMAGE" || "$FED_IMAGE" =~ ^sovryn/fed-tokenbridge:[A-Za-z0-9_.-]+@sha256:[0-9a-f]{64}$ ]] || parameter_error 'Image must be the approved tag@sha256:digest'
[[ -t 0 ]] || parameter_error 'Run in an interactive Bash terminal; no yes/force mode exists'
test "$(id -u)" = 1000 || parameter_error 'Use the deployment user UID1000, without sudo'
export DOCKER_HOST=unix:///var/run/docker.sock
for program in docker git python3 sha256sum timeout flock cmp; do
  command -v "$program" >/dev/null || parameter_error "Required program missing: $program"
done
on_error() {
  result=$1
  trap - ERR
  printf '\nStopped at: %s (exit %s). No automatic retry or rollback.\n' "$STAGE" "$result" >&2
  if [[ -n "$OPS_DIR" ]]; then printf 'Keep this private run directory: %s\n' "$OPS_DIR" >&2; fi
  exit "$result"
}
trap 'on_error $?' ERR
BASE_DIR="$HOME/.local/share/bridge-ops"
test ! -L "$BASE_DIR"
mkdir -p "$BASE_DIR"
test -O "$BASE_DIR"
chmod 700 "$BASE_DIR"
test ! -L "$BASE_DIR/eth-upgrade.lock"
exec 9>"$BASE_DIR/eth-upgrade.lock"
flock -n 9 || parameter_error 'Another ETH upgrade/rollback is running'
confirm() { local answer; read -r -p "$1 [y/N] " answer; [[ "$answer" == y || "$answer" == Y || "$answer" == yes ]]; }
step() { STAGE=$1; printf '\n%s\n' "$1"; }
require_inputs() {
  [[ -n "$REPAIR_REVISION" ]] || read -r -p 'Approved full release commit: ' REPAIR_REVISION
  [[ -n "$FED_IMAGE" ]] || read -r -p 'Approved image tag@sha256:digest: ' FED_IMAGE
  [[ -n "$RELEASE_OVERRIDE" ]] || read -r -p 'Absolute path to supplied Compose override: ' RELEASE_OVERRIDE
  [[ -n "$PUBLIC_OPERATOR" ]] || read -r -p 'Node label (fed_1..fed_5): ' PUBLIC_OPERATOR
  [[ -n "$EXPECTED_SIGNER" ]] || read -r -p 'Your approved FEDERATOR public address: ' EXPECTED_SIGNER
  [[ "$REPAIR_REVISION" =~ ^[0-9a-f]{40}$ ]] || parameter_error 'Invalid release commit'
  APP_REVISION=${APP_REVISION:-$REPAIR_REVISION}
  [[ "$APP_REVISION" =~ ^[0-9a-f]{40}$ ]] || parameter_error 'Invalid application commit'
  [[ "$FED_IMAGE" =~ ^sovryn/fed-tokenbridge:[A-Za-z0-9_.-]+@sha256:[0-9a-f]{64}$ ]] || parameter_error 'Invalid image tag@digest'
  [[ "$PUBLIC_OPERATOR" =~ ^fed_[1-5]$ ]] || parameter_error 'Invalid fed_n label'
  [[ "$EXPECTED_SIGNER" =~ ^0x[0-9a-fA-F]{40}$ ]] || parameter_error 'Invalid public signer'
  [[ "$RELEASE_OVERRIDE" == /* && -f "$RELEASE_OVERRIDE" && ! -L "$RELEASE_OVERRIDE" ]] || parameter_error 'Supplied override must be a regular absolute-path file'
  OPERATOR=$PUBLIC_OPERATOR
  export FED_REPO REPAIR_REVISION APP_REVISION FED_IMAGE RELEASE_OVERRIDE PUBLIC_OPERATOR EXPECTED_SIGNER KEY_SOURCE OPERATOR
}
verify_bundle() {
  for file in federator_recovery.py federator_dependencies.py federator_watcher.py etherscan_prerequisite.py dd_agent_recovery.py federator_datadog_upgrade.py federator_upgrade_safety.py federator_compose_plan.py; do
    test -f "$OPS_DIR/$file" && test ! -L "$OPS_DIR/$file"
    test "$(git -C "$FED_REPO" hash-object "$OPS_DIR/$file")" = "$(git -C "$FED_REPO" rev-parse "$REPAIR_REVISION:tools/$file")"
  done
}
write_context() {
python3 - <<'PY'
import json,os
from pathlib import Path
fields=('FED_REPO','REPAIR_REVISION','FED_IMAGE','RELEASE_OVERRIDE','PUBLIC_OPERATOR','EXPECTED_SIGNER','KEY_SOURCE','COMPOSE_PROJECT','CONFIG_DIR','WATCH_SECONDS','COMPOSE_PLAN_SHA256','APP_REVISION')
with (Path(os.environ['OPS_DIR'])/'upgrade-context.json').open('x') as out:
 json.dump({name:os.environ[name] for name in fields},out,indent=2)
PY
}
run_watcher() {
  step 'Watching federator and Datadog for the requested duration'
  REPORT_DIR="$OPS_DIR/watcher"
  if [[ -n "$ROLLBACK_RUN" ]]; then REPORT_DIR="$OPS_DIR/watcher-rollback"; fi
  if python3 "$OPS_DIR/federator_watcher.py" --operator "$PUBLIC_OPERATOR" --profile eth-rsk --duration "$WATCH_SECONDS" --output-dir "$REPORT_DIR"; then
    status=0
  else
    status=$?
  fi
  printf '\nSend these two reports:\n%s/summary.md\n%s/report.json\n' "$REPORT_DIR" "$REPORT_DIR"
  printf 'Keep the image backup private until recovery is accepted. Watcher exit: %s\n' "$status"
  return "$status"
}

prepare() {
set -euo pipefail
umask 077
export DOCKER_HOST=unix:///var/run/docker.sock
KEY_SOURCE=${KEY_SOURCE:-aws}
case "$KEY_SOURCE" in aws|manual) ;; *) printf 'KEY_SOURCE must be aws or manual.\n'; exit 1 ;; esac
export KEY_SOURCE
CONFIG_DIR="$FED_REPO/federator-env/mainnet-ETH-RSK"
export OPERATOR PUBLIC_OPERATOR EXPECTED_SIGNER FED_REPO CONFIG_DIR REPAIR_REVISION
test "$(id -u)" = 1000
docker --host unix:///var/run/docker.sock compose version
git -C "$FED_REPO" rev-parse HEAD > "$OPS_DIR/old-host-revision.txt"
ORIGIN_URL=$(git -C "$FED_REPO" remote get-url origin)
case "$ORIGIN_URL" in
  https://github.com/DistributedCollective/Bridge-SC|https://github.com/DistributedCollective/Bridge-SC.git|git@github.com:DistributedCollective/Bridge-SC|git@github.com:DistributedCollective/Bridge-SC.git|ssh://git@github.com/DistributedCollective/Bridge-SC.git) ;;
  *) parameter_error 'Unexpected origin; use the approved Bridge-SC checkout' ;;
esac
git -C "$FED_REPO" fetch --no-tags origin federator-diagnostics-recovery-upgrade
test "$(git -C "$FED_REPO" rev-parse --verify "$REPAIR_REVISION^{commit}")" = "$REPAIR_REVISION"
git -C "$FED_REPO" merge-base --is-ancestor "$REPAIR_REVISION" FETCH_HEAD
for file in federator_watcher.py federator_dependencies.py federator_recovery.py etherscan_prerequisite.py dd_agent_recovery.py federator_datadog_upgrade.py federator_upgrade_safety.py federator_compose_plan.py; do
  git -C "$FED_REPO" show "$REPAIR_REVISION:tools/$file" > "$OPS_DIR/$file"
done
for file in federator_watcher.py federator_dependencies.py federator_recovery.py etherscan_prerequisite.py dd_agent_recovery.py federator_datadog_upgrade.py federator_upgrade_safety.py federator_compose_plan.py; do
  test "$(git -C "$FED_REPO" hash-object "$OPS_DIR/$file")" = "$(git -C "$FED_REPO" rev-parse "$REPAIR_REVISION:tools/$file")"
done
python3 - <<'PY'
import json,os,sys,subprocess
from pathlib import Path
sys.path.insert(0,os.environ['OPS_DIR'])
import federator_recovery as r
node=r.Node(Path(os.environ['FED_REPO']),'eth-rsk','bridge-sc_federation_1')
s=node.inspect()  # verifies the exact ETH config/database mounts and supported user/image
r.load_public_config(node)
import federator_dependencies as fd
public=fd.public_settings(node.cfg,'eth-rsk')
if public['configured_signer']!=os.environ['EXPECTED_SIGNER'].lower():
 raise SystemExit('Supplied federator signer disagrees with config; do not upgrade')
if public['minimum_peers']!=2:raise SystemExit('Unexpected peer gate; request the matching release')
labels=json.loads(subprocess.check_output(['docker','--host','unix:///var/run/docker.sock','inspect',s['id'],'--format','{{json .Config.Labels}}'],text=True))
project=labels.get('com.docker.compose.project')
if not project or labels.get('com.docker.compose.service')!='federation':
 raise SystemExit('This is not the expected Compose federation service. Send coordinator the report; do not replace it.')
s['compose_project']=project
p=Path(os.environ['OPS_DIR'])/'before.json';p.write_text(json.dumps(s,indent=2)+'\n');p.chmod(0o600)
print('Verified existing ETH container. Private release records:',p.parent)
PY
python3 "$OPS_DIR/federator_dependencies.py" --profile eth-rsk \
  --repo "$FED_REPO" --versions-only --output "$OPS_DIR/before-versions.json" || \
  printf 'Version report contains unavailable/failed checks; send it for review.\n'
printf 'Preparation report: %s\n' "$OPS_DIR/before-versions.json"
}

verify_image() {
export FED_IMAGE RELEASE_OVERRIDE
[[ "$FED_IMAGE" =~ ^sovryn/fed-tokenbridge:[A-Za-z0-9_.-]+@sha256:[0-9a-f]{64}$ ]]
[[ "$RELEASE_OVERRIDE" == /* ]] && test -f "$RELEASE_OVERRIDE" && test ! -L "$RELEASE_OVERRIDE"
timeout 300s docker --host unix:///var/run/docker.sock pull "$FED_IMAGE"
EXPECTED_IMAGE_ID=$(docker --host unix:///var/run/docker.sock image inspect "$FED_IMAGE" --format '{{.Id}}')
export EXPECTED_IMAGE_ID
test "$(docker --host unix:///var/run/docker.sock image inspect "$FED_IMAGE" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = "$APP_REVISION"
python3 - <<'PY' > "$OPS_DIR/repair-source-hashes.json"
import hashlib,json,os,subprocess
prefix='sovryn-token-bridge/federator/'
files=['src/lib/GasPriceAvg.js','src/lib/GasPriceFetcher.js','src/lib/GasServices.js','src/lib/TransactionSender.js','src/vendors/RSKKeyedAuth.js']
print(json.dumps({p:hashlib.sha256(subprocess.check_output(['git','-C',os.environ['FED_REPO'],'show',os.environ['APP_REVISION']+':'+prefix+p])).hexdigest() for p in files}))
PY
PUBLIC_HASHES=$(cat "$OPS_DIR/repair-source-hashes.json")
docker --host unix:///var/run/docker.sock run --rm --network none --read-only --log-driver none --cap-drop ALL \
  --security-opt no-new-privileges --user 1000:1000 --entrypoint node \
  --workdir /app/federator -e "EXPECTED_HASHES=$PUBLIC_HASHES" "$FED_IMAGE" -e '
const fs=require("fs"),crypto=require("crypto"),assert=require("assert");
for(const [p,want] of Object.entries(JSON.parse(process.env.EXPECTED_HASHES))){
 assert.strictEqual(crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex"),want);
}
require("ataraxia-tcp");require("@ethereumjs/tx");
console.log("Repair source hashes and native module imports passed");'
unset PUBLIC_HASHES
COMPOSE_PROJECT=$(python3 -c 'import json,os;from pathlib import Path;print(json.loads((Path(os.environ["OPS_DIR"])/"before.json").read_text())["compose_project"])')
export COMPOSE_PROJECT FED_ENV=mainnet-ETH-RSK
git -C "$FED_REPO" show "$REPAIR_REVISION:docker-compose-prod.yml" | \
  python3 "$OPS_DIR/federator_compose_plan.py" --base "$OPS_DIR/docker-compose-prod.yml"
COMPOSE=(docker --host unix:///var/run/docker.sock compose --project-directory "$FED_REPO" --project-name "$COMPOSE_PROJECT" \
  -f "$OPS_DIR/docker-compose-prod.yml" -f "$RELEASE_OVERRIDE")
# Parse without interpolation, then discard the Agent and its unused resources.
# Only the selected ETH service may resolve environment variables.
"${COMPOSE[@]}" config --no-interpolate --format json | \
  python3 "$OPS_DIR/federator_compose_plan.py" --model "$OPS_DIR/federation-input.private.json"
COMPOSE=(docker --host unix:///var/run/docker.sock compose --project-directory "$FED_REPO" --project-name "$COMPOSE_PROJECT" -f "$OPS_DIR/federation-input.private.json")
"${COMPOSE[@]}" config --format json | python3 -c '
import json,os
full=json.load(__import__("sys").stdin);s=full["services"]["federation"]
assert s["image"]==os.environ["FED_IMAGE"]
assert s["container_name"]=="bridge-sc_federation_1"
v=s["volumes"];assert len(v)==2
assert {x["target"]:(x["type"],x["source"],x.get("read_only",False)) for x in v}=={
 "/app/federator/config":("bind",os.environ["CONFIG_DIR"],False),
 "/app/federator/db":("bind",os.environ["CONFIG_DIR"]+"/db",False)}
p=s["ports"];assert len(p)==1 and str(p[0]["published"])=="4444" and p[0]["target"]==30303
assert s.get("restart","no")=="no";assert s["user"]=="1000:1000"
assert s["environment"]["TZ"]=="UTC"
assert s["logging"]["driver"]=="json-file"
assert s["logging"]["options"]=={"max-size":"20m","max-file":"5"}
# Freeze only this resolved service and its top-level declarations, not the Agent.
plan={k:full[k] for k in ("name","networks","volumes","secrets","configs") if k in full}
plan["services"]={"federation":s}
def literal(value):
 if isinstance(value,str):return value.replace("$","$$")
 if isinstance(value,list):return [literal(x) for x in value]
 if isinstance(value,dict):return {k:literal(v) for k,v in value.items()}
 return value
from pathlib import Path
with (Path(os.environ["OPS_DIR"])/"deployment.private.json").open("x") as out:json.dump(literal(plan),out)
print("Image, original mounts and private deployment plan verified")'
COMPOSE_PLAN_SHA256=$(sha256sum "$OPS_DIR/deployment.private.json" | cut -d ' ' -f 1)
export COMPOSE_PLAN_SHA256
COMPOSE=(docker --host unix:///var/run/docker.sock compose --project-directory "$FED_REPO" --project-name "$COMPOSE_PROJECT" -f "$OPS_DIR/deployment.private.json")
"${COMPOSE[@]}" config --quiet
}


backup_image() {
set -euo pipefail
umask 077
OLD_IMAGE_ID=$(python3 -c 'import json,os;from pathlib import Path;print(json.loads((Path(os.environ["OPS_DIR"])/"before.json").read_text())["image_id"])')
[[ "$OLD_IMAGE_ID" =~ ^sha256:[0-9a-f]{64}$ ]]
ROLLBACK_DIR="$OPS_DIR/rollback"
export OLD_IMAGE_ID ROLLBACK_DIR
mkdir -m 700 "$ROLLBACK_DIR"
python3 - <<'PY'
import json,os,shutil,subprocess
from pathlib import Path
root=Path(os.environ['ROLLBACK_DIR'])
info=json.loads(subprocess.check_output(['docker','--host','unix:///var/run/docker.sock','image','inspect',os.environ['OLD_IMAGE_ID']],text=True))[0]
if info['Id']!=os.environ['OLD_IMAGE_ID']:raise SystemExit('Original image identity mismatch')
size=info.get('Size',0)
if not isinstance(size,int) or size<=0:raise SystemExit('Original image size unavailable')
if shutil.disk_usage(root).free < size*2 + 2*1024**3:
 raise SystemExit('Insufficient disk for an image archive with reserve. Stop; arrange private backup storage.')
(root/'old-image-metadata.json').write_text(json.dumps({k:info.get(k) for k in ('Id','RepoDigests','Os','Architecture','Size')},indent=2)+'\n')
(root/'old-image-id.txt').write_text(info['Id']+'\n')
PY
OLD_CONTAINER_ID=$(python3 -c 'import json,os;from pathlib import Path;print(json.loads((Path(os.environ["OPS_DIR"])/"before.json").read_text())["id"])')
docker --host unix:///var/run/docker.sock inspect "$OLD_CONTAINER_ID" > "$ROLLBACK_DIR/old-container.private.json"
timeout --kill-after=10s 600s docker --host unix:///var/run/docker.sock image save \
  --output "$ROLLBACK_DIR/old-image.tar.partial" "$OLD_IMAGE_ID"
python3 - <<'PY'
import hashlib,json,os,tarfile
from pathlib import Path
root=Path(os.environ['ROLLBACK_DIR']);path=root/'old-image.tar.partial'
with tarfile.open(path,'r:') as archive:
 manifest=json.load(archive.extractfile('manifest.json'))
 if len(manifest)!=1:raise SystemExit('Expected one original image in backup')
 entry=manifest[0];config=archive.extractfile(entry['Config']).read()
 if 'sha256:'+hashlib.sha256(config).hexdigest()!=os.environ['OLD_IMAGE_ID']:
  raise SystemExit('Backup does not contain the original image config')
 for layer in entry['Layers']:
  if not archive.getmember(layer).isfile():raise SystemExit('Image layer missing from archive')
path.rename(root/'old-image.tar')
PY
(cd "$ROLLBACK_DIR"; sha256sum old-image.tar > old-image.sha256; sha256sum -c old-image.sha256)
chmod 600 "$ROLLBACK_DIR"/*
printf 'Verified private image backup: %s\n' "$ROLLBACK_DIR"
}

stop_original() {
(cd "$ROLLBACK_DIR"; sha256sum -c old-image.sha256)
test "$(cat "$ROLLBACK_DIR/old-image-id.txt")" = "$OLD_IMAGE_ID"
python3 - <<'PY'
import hashlib,json,os,sys
from pathlib import Path
sys.path.insert(0,os.environ['OPS_DIR']);import federator_recovery as r
node=r.Node(Path(os.environ['FED_REPO']),'eth-rsk','bridge-sc_federation_1')
old=json.loads((Path(os.environ['OPS_DIR'])/'before.json').read_text());s=node.inspect()
if (s['id'],s['image_id'])!=(old['id'],old['image_id']):raise SystemExit('Existing container changed. Do not stop it; send coordinator the error.')
if s['running']:node.runner.run(['docker','stop','--time','30',s['id']],timeout=45)
if node.inspect()['running']:raise SystemExit('Stop not confirmed')
import federator_watcher as fw
raw,error=fw.fixed_command(fw.Runner(),['docker','logs','--timestamps','--tail','1000',s['id']],timeout=8,limit=512*1024)
prior={'capturedUtc':r.utc_now(),'status':'unavailable' if error else 'captured','failure':error,'markers':fw.markers(raw or '')}
markers_path=Path(os.environ['OPS_DIR'])/'before-markers.json';markers_path.write_text(json.dumps(prior,indent=2)+'\n');markers_path.chmod(0o600)
def snapshot():
 out={}
 for name in ('db/lastBlock.txt','db/side-fed/lastBlock.txt'):
  p=r.safe_path(node.cfg/name,node.cfg/'db')
  out[name]=r.read_checkpoint(p,node.cfg/'db') if p.parent.exists() else None
 for name in ('config.js','mainnet.json','rskmainnet.json','peers.config.js'):
  p=node.cfg/name
  if p.is_symlink():raise SystemExit('Unexpected config symlink')
  out[name]=hashlib.sha256(p.read_bytes()).hexdigest()
 out['directories']={str(p):[p.stat().st_dev,p.stat().st_ino] for p in (node.cfg,node.cfg/'db')}
 return out
p=Path(os.environ['OPS_DIR'])/'stopped-state.json';p.write_text(json.dumps(snapshot(),indent=2)+'\n');p.chmod(0o600)
print('Only the ETH federator is stopped. Original config/cursor metadata recorded.')
PY
}

restore_key() {
set +x
python3 - <<'PY'
import getpass,os,stat,sys,warnings
from pathlib import Path
sys.path.insert(0,os.environ['OPS_DIR']);import federator_recovery as r
node=r.Node(Path(os.environ['FED_REPO']),'eth-rsk','bridge-sc_federation_1',allow_created=True)
if node.inspect()['running']:raise SystemExit('Federator must stay stopped for key restoration')
key=node.cfg/'federator.key'
if key.is_symlink():raise SystemExit('Unexpected key symlink')
if key.exists():
 m=key.stat()
 if not stat.S_ISREG(m.st_mode) or m.st_uid!=1000:raise SystemExit('Key ownership/type needs review')
 if m.st_size==0:key.unlink()
if not key.exists():
 def confirm(question):
  print(question+' [y/N] ',end='',flush=True)
  with open('/dev/tty') as tty:return tty.readline().strip().lower() in ('y','yes')
 source=os.environ.get('KEY_SOURCE','aws')
 if source=='manual':
  warnings.simplefilter('error',getpass.GetPassWarning)
  value=getpass.getpass('Paste ORIGINAL federator private key (hidden): ')
  if node.inspect()['running']:raise SystemExit('Container started independently; key left unchanged')
  r.install_key(node.cfg,value,node.expected_uid)
  del value
 elif source=='aws':
  if not r.restore_original_key(node,confirm):raise SystemExit('Original key restoration declined')
 else:raise SystemExit('KEY_SOURCE must be aws or manual')
node.key_ready()
print('Private key file ownership/mode/format passed; public signer verification follows.')
PY

}

activate() {
"${COMPOSE[@]}" up --no-start --no-deps --no-build --pull never --force-recreate federation
python3 - <<'PY'
import hashlib,json,os,subprocess,sys
from pathlib import Path
sys.path.insert(0,os.environ['OPS_DIR']);import federator_recovery as r
old=json.loads((Path(os.environ['OPS_DIR'])/'before.json').read_text())
s=json.loads(subprocess.check_output(['docker','--host','unix:///var/run/docker.sock','inspect','bridge-sc_federation_1','--format','{"id":{{json .Id}},"image":{{json .Image}},"running":{{.State.Running}},"mounts":{{json .Mounts}}}'],text=True))
if s['running'] or s['image']!=os.environ['EXPECTED_IMAGE_ID'] or s['id']==old['id']:raise SystemExit('Replacement image/stopped state incorrect; do not start')
cfg=Path(os.environ['CONFIG_DIR']);mounts={x['Destination']:x['Source'] for x in s['mounts']}
if mounts!={'/app/federator/config':str(cfg),'/app/federator/db':str(cfg/'db')}:raise SystemExit('Replacement mounts incorrect; do not start')
now={}
for name in ('db/lastBlock.txt','db/side-fed/lastBlock.txt'):
 p=r.safe_path(cfg/name,cfg/'db');now[name]=r.read_checkpoint(p,cfg/'db') if p.parent.exists() else None
for name in ('config.js','mainnet.json','rskmainnet.json','peers.config.js'):now[name]=hashlib.sha256((cfg/name).read_bytes()).hexdigest()
now['directories']={str(p):[p.stat().st_dev,p.stat().st_ino] for p in (cfg,cfg/'db')}
if now!=json.loads((Path(os.environ['OPS_DIR'])/'stopped-state.json').read_text()):raise SystemExit('Config or cursors changed; do not start')
p=Path(os.environ['OPS_DIR'])/'replacement.json';p.write_text(json.dumps(s,indent=2)+'\n');p.chmod(0o600)
print('New image is staged. Original config, directory identities and both numeric checkpoints match.')
PY
# Operator activation: this enables the node's normal signing/transaction submission.
python3 "$OPS_DIR/federator_upgrade_safety.py" --repo "$FED_REPO" --start-cleanup "$EXPECTED_IMAGE_ID" --expected-signer "$EXPECTED_SIGNER" --output "$OPS_DIR/startup-key-cleanup.json"
docker --host unix:///var/run/docker.sock inspect bridge-sc_federation_1 \
  --format 'status={{.State.Status}} image={{.Image}} started={{.State.StartedAt}} oom={{.State.OOMKilled}}'
}


capture_current_state() {
python3 - <<'PY'
import hashlib,json,os,sys
from pathlib import Path
sys.path.insert(0,os.environ['OPS_DIR']);import federator_recovery as r
node=r.Node(Path(os.environ['FED_REPO']),'eth-rsk','bridge-sc_federation_1',allow_created=True)
if node.inspect()['running']:raise SystemExit('State snapshot requires a stopped ETH node')
state={}
for name in ('db/lastBlock.txt','db/side-fed/lastBlock.txt'):
 p=r.safe_path(node.cfg/name,node.cfg/'db')
 state[name]=r.read_checkpoint(p,node.cfg/'db') if p.parent.exists() else None
for name in ('config.js','mainnet.json','rskmainnet.json','peers.config.js'):
 p=r.safe_path(node.cfg/name,node.cfg)
 state[name]=hashlib.sha256(p.read_bytes()).hexdigest()
state['directories']={str(p):[p.stat().st_dev,p.stat().st_ino] for p in (node.cfg,node.cfg/'db')}
print(json.dumps(state,sort_keys=True))
PY
}

stage_rollback() {
set -euo pipefail
export ROLLBACK_DIR="$OPS_DIR/rollback"
(cd "$ROLLBACK_DIR"; sha256sum -c old-image.sha256)
OLD_IMAGE_ID=$(cat "$ROLLBACK_DIR/old-image-id.txt")
[[ "$OLD_IMAGE_ID" =~ ^sha256:[0-9a-f]{64}$ ]]
export OLD_IMAGE_ID
python3 - <<'PY'
import json,os,subprocess
from pathlib import Path
old=json.loads((Path(os.environ['OPS_DIR'])/'before.json').read_text())
if old['image_id']!=os.environ['OLD_IMAGE_ID']:raise SystemExit('Backup image does not match original release record')
p=Path(os.environ['OPS_DIR'])/'replacement.json'
if not p.is_file():raise SystemExit('Staging did not finish; coordinator must inspect before rollback')
replacement=json.loads(p.read_text())
s=json.loads(subprocess.check_output(['docker','--host','unix:///var/run/docker.sock','inspect','bridge-sc_federation_1','--format','{"id":{{json .Id}},"image":{{json .Image}},"running":{{.State.Running}}}'],text=True))
if (s['id'],s['image'])!=(replacement['id'],replacement['image']):raise SystemExit('Current container changed; do not stop or replace it blindly')
if s['running']:subprocess.run(['docker','--host','unix:///var/run/docker.sock','stop','--time','30',s['id']],check=True,timeout=45)
PY
capture_current_state > "$OPS_DIR/rollback-stopped-state.json"
python3 "$OPS_DIR/federator_upgrade_safety.py" --repo "$FED_REPO" --archive-history --output "$OPS_DIR/rollback-history"
timeout --kill-after=10s 600s docker --host unix:///var/run/docker.sock image load --input "$ROLLBACK_DIR/old-image.tar"
test "$(docker --host unix:///var/run/docker.sock image inspect "$OLD_IMAGE_ID" --format '{{.Id}}')" = "$OLD_IMAGE_ID"
ROLLBACK_IMAGE="sovryn/fed-tokenbridge:eth-rollback-${OLD_IMAGE_ID:7:12}-$(date -u '+%Y%m%dT%H%M%SZ')"
export ROLLBACK_IMAGE
# The new tag references exactly the verified original image; no registry pull.
docker --host unix:///var/run/docker.sock image tag "$OLD_IMAGE_ID" "$ROLLBACK_IMAGE"
python3 - <<'PY'
import json,os
from pathlib import Path
p=Path(os.environ['ROLLBACK_DIR'])/'rollback-image.json'
with p.open('x') as out:json.dump({'services':{'federation':{'image':os.environ['ROLLBACK_IMAGE']}}},out)
PY
ROLLBACK_COMPOSE=("${COMPOSE[@]}" -f "$ROLLBACK_DIR/rollback-image.json")
"${ROLLBACK_COMPOSE[@]}" up --no-start --no-deps --no-build --pull never --force-recreate federation
python3 - <<'PY'
import os,sys
from pathlib import Path
sys.path.insert(0,os.environ['OPS_DIR']);import federator_recovery as r
node=r.Node(Path(os.environ['FED_REPO']),'eth-rsk','bridge-sc_federation_1',allow_created=True)
s=node.inspect()
if s['running'] or s['image_id']!=os.environ['OLD_IMAGE_ID']:
 raise SystemExit('Rollback image/stopped state incorrect; do not start')
print('Original image staged and original config/DB mounts verified; activation remains held.')
PY
capture_current_state > "$OPS_DIR/rollback-after-state.json"
cmp -s "$OPS_DIR/rollback-stopped-state.json" "$OPS_DIR/rollback-after-state.json"
}

if [[ -n "$ROLLBACK_RUN" ]]; then
  step 'Read the saved rollback context'
  [[ "$ROLLBACK_RUN" == /* && -d "$ROLLBACK_RUN" && ! -L "$ROLLBACK_RUN" && -O "$ROLLBACK_RUN" ]] || parameter_error 'Use the absolute private directory printed by this upgrade'
  OPS_DIR=$ROLLBACK_RUN
  export OPS_DIR
  # Strict JSON/NUL fields, never source/eval a saved shell file.
  CONTEXT_FIELDS=$(mktemp "$BASE_DIR/rollback-context.XXXXXX")
  python3 - "$OPS_DIR" > "$CONTEXT_FIELDS" <<'PY'
import json,os,stat,sys
from pathlib import Path
root=Path(sys.argv[1]);path=root/'upgrade-context.json'
if path.is_symlink() or path.stat().st_uid!=os.getuid() or stat.S_IMODE(path.stat().st_mode)!=0o600:
 raise SystemExit('Unsafe rollback context')
value=json.loads(path.read_text())
fields=('FED_REPO','REPAIR_REVISION','FED_IMAGE','RELEASE_OVERRIDE','PUBLIC_OPERATOR','EXPECTED_SIGNER','KEY_SOURCE','COMPOSE_PROJECT','CONFIG_DIR','WATCH_SECONDS','COMPOSE_PLAN_SHA256','APP_REVISION')
for name in fields:
 item=value.get(name,value.get('REPAIR_REVISION') if name=='APP_REVISION' else None)
 if not isinstance(item,str) or '\0' in item:raise SystemExit('Invalid rollback context')
 sys.stdout.buffer.write(item.encode()+b'\0')
PY
  SAVED=()
  while IFS= read -r -d '' value; do SAVED+=("$value"); done < "$CONTEXT_FIELDS"
  rm -- "$CONTEXT_FIELDS"
  ((${#SAVED[@]}==12)) || parameter_error 'Incomplete rollback context'
  [[ -z "$REPO_OVERRIDE" || "$REPO_OVERRIDE" == "${SAVED[0]}" ]] || parameter_error 'Repo differs from saved upgrade; use the original run'
  FED_REPO=${SAVED[0]}; REPAIR_REVISION=${SAVED[1]}; FED_IMAGE=${SAVED[2]}; RELEASE_OVERRIDE=${SAVED[3]}
  PUBLIC_OPERATOR=${SAVED[4]}; EXPECTED_SIGNER=${SAVED[5]}; KEY_SOURCE=${SAVED[6]}; COMPOSE_PROJECT=${SAVED[7]}
  CONFIG_DIR=${SAVED[8]}; WATCH_SECONDS=${SAVED[9]}; COMPOSE_PLAN_SHA256=${SAVED[10]}; APP_REVISION=${SAVED[11]}
  if [[ "$KEY_SOURCE_OVERRIDE" == true ]]; then KEY_SOURCE=manual; fi
  if [[ -n "$WATCH_OVERRIDE" ]]; then WATCH_SECONDS=$WATCH_OVERRIDE; fi
  test "$CONFIG_DIR" = "$FED_REPO/federator-env/mainnet-ETH-RSK"
  export FED_ENV=mainnet-ETH-RSK
  export FED_REPO REPAIR_REVISION APP_REVISION FED_IMAGE RELEASE_OVERRIDE PUBLIC_OPERATOR EXPECTED_SIGNER KEY_SOURCE COMPOSE_PROJECT CONFIG_DIR WATCH_SECONDS
  [[ "$REPAIR_REVISION" =~ ^[0-9a-f]{40}$ && "$PUBLIC_OPERATOR" =~ ^fed_[1-5]$ && "$EXPECTED_SIGNER" =~ ^0x[0-9a-fA-F]{40}$ ]] || parameter_error 'Invalid rollback release/signer context'
  [[ "$KEY_SOURCE" == aws || "$KEY_SOURCE" == manual ]] || parameter_error 'Invalid saved key source'
  [[ "$WATCH_SECONDS" =~ ^[0-9]{1,5}$ ]] && ((10#$WATCH_SECONDS>=1 && 10#$WATCH_SECONDS<=86400)) || parameter_error 'Invalid saved watcher duration'
  test "$(git -C "$FED_REPO" hash-object "$SCRIPT_FILE")" = "$(git -C "$FED_REPO" rev-parse "$REPAIR_REVISION:tools/upgrade-eth-federator.sh")"
  verify_bundle
  [[ "$COMPOSE_PLAN_SHA256" =~ ^[0-9a-f]{64}$ ]]
  test -f "$OPS_DIR/deployment.private.json" && test ! -L "$OPS_DIR/deployment.private.json"
  test "$(sha256sum "$OPS_DIR/deployment.private.json" | cut -d ' ' -f 1)" = "$COMPOSE_PLAN_SHA256"
  COMPOSE=(docker --host unix:///var/run/docker.sock compose --project-directory "$FED_REPO" --project-name "$COMPOSE_PROJECT" -f "$OPS_DIR/deployment.private.json")
  "${COMPOSE[@]}" config --quiet
  python3 "$OPS_DIR/federator_datadog_upgrade.py" --verify "$OPS_DIR/datadog-state" --allow-source-handoff
  confirm 'Restore the original ETH image from this archive now?' || exit 0
  step 'Restore and stage the original image'
  stage_rollback
  FED_IMAGE=$ROLLBACK_IMAGE; export FED_IMAGE
  step 'Restore/check the original key and public signer'
  restore_key
  confirm 'Start the restored ETH node in the agreed window now?' || exit 0
  python3 "$OPS_DIR/federator_upgrade_safety.py" --repo "$FED_REPO" --start-cleanup "$OLD_IMAGE_ID" --expected-signer "$EXPECTED_SIGNER" --output "$OPS_DIR/rollback-startup-key-cleanup.json"
  python3 "$OPS_DIR/federator_datadog_upgrade.py" --verify "$OPS_DIR/datadog-state" --allow-source-handoff
  run_watcher
else
  require_inputs
  step '1/7 Fetch and verify the pinned upgrade tools'
  OPS_DIR=$(mktemp -d "$BASE_DIR/eth-upgrade.XXXXXX"); export OPS_DIR
  prepare
  test "$(git -C "$FED_REPO" hash-object "$SCRIPT_FILE")" = "$(git -C "$FED_REPO" rev-parse "$REPAIR_REVISION:tools/upgrade-eth-federator.sh")"
  cp -- "$SCRIPT_FILE" "$OPS_DIR/upgrade.sh"
  chmod 600 "$OPS_DIR/upgrade.sh"
  step '2/7 Check the Etherscan key before stopping anything'
  python3 "$OPS_DIR/etherscan_prerequisite.py" "$CONFIG_DIR"
  step 'Check Datadog compatibility before stopping either service'
  python3 "$OPS_DIR/federator_datadog_upgrade.py" --inspect "$OPS_DIR/datadog-preflight"
  step '3/7 Download and verify the approved image and Compose plan'
  verify_image
  export WATCH_SECONDS
  write_context
  confirm 'Upgrade this ETH node and repair Datadog if needed in the agreed window now?' || exit 0
  step '4/7 Back up and verify the original image'
  backup_image
  step 'Repair Datadog if needed and retain its checkpoint volume'
  python3 "$OPS_DIR/federator_datadog_upgrade.py" --capture "$OPS_DIR/datadog-state"
  step '5/7 Stop only the ETH federator and record checkpoints'
  stop_original
  step 'Archive and verify retained local logs and launch configuration'
  python3 "$OPS_DIR/federator_upgrade_safety.py" --repo "$FED_REPO" --archive-history --output "$OPS_DIR/history"
  step '6/7 Restore/check the original federator key and public signer'
  restore_key
  step '7/7 Stage, verify and start the new image'
  activate
  python3 "$OPS_DIR/federator_datadog_upgrade.py" --verify "$OPS_DIR/datadog-state" --allow-source-handoff
  run_watcher
fi
