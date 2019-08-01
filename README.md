# Messing around with litex ...

## my setup
starting from the beginning on debian

```bash
sudo apt install libevent-dev libjson-c-dev
sudo pip3 install virtualenvwrapper
mkvirtualenv litex
git clone git@github.com:yetifrisstlama/litex.git --recursive
cd litex
python litex_setup.py init
python litex_setup.py install
python setup.py develop
```
