#! /bin/bash
# check that we are root
if [ "$EUID" -ne 0 ]
  then echo "This script requires root to bind the necessary interfaces."
  exit
fi

# install gvproxy from https://github.com/brave-intl/bat-go.git
# docker run --rm -it -v $(pwd):/pwd nitro-shim:latest cp gvproxy /pwd/
# cp gvproxy /usr/bin/
gvproxy -listen vsock://:1024 -listen unix:///tmp/network.sock &
pid=$!
sleep 1

curl \
  --unix-socket /tmp/network.sock \
  http:/unix/services/forwarder/expose \
  -X POST \
  -d '{"local":":443","remote":"192.168.127.2:443"}'

wait $pid
