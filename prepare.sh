set -ex

DEFAULT_FIBER_BRANCH="quake/refactor-store-rpc"
DEFAULT_FIBER_URL="https://github.com/quake/fiber.git"

GitFIBERBranch="${GitBranch:-$DEFAULT_FIBER_BRANCH}"
GitFIBERUrl="${GitUrl:-$DEFAULT_FIBER_URL}"

cp download/0.202.0/ckb-cli ./source/ckb-cli
git clone -b $GitFIBERBranch $GitFIBERUrl
cd fiber
cargo build
cp target/debug/fnn ../download/fiber/current/fnn.debug
cp target/debug/fnn-cli ../download/fiber/current/fnn-cli.debug
cargo build --release
cp target/release/fnn ../download/fiber/current/fnn
cp target/release/fnn-cli ../download/fiber/current/fnn-cli
cargo build --release --features sqlite
cp target/release/fnn ../download/fiber/current/fnn.sqlite
cp target/release/fnn-cli ../download/fiber/current/fnn-cli.sqlite
