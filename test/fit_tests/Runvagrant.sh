#!/biin/bash
# This file is for running Vagrant Smoke test from Jenkins
vagrant -f destroy template
vagrant -f destroy quanta_d51
vagrant up template
rm -rf myenv_hwimobuild
virtualenv myenv_hwimobuild
source myenv_hwimobuild/bin/activate
pip install -r requirements.txt > pipinstall.log
python run_tests.py -stack vagrant_remote -xunit -config config.vagrant -test deploy/rackhd_source_install.py
python run_tests.py -stack vagrant_remote -xunit -config config.vagrant -test deploy/rackhd_stack_init.py:rackhd_stack_init.test01_preload_sku_packs
vagrant up quanta_d51
python run_tests.py -stack vagrant_remote -xunit -config config.vagrant -test deploy/rackhd_stack_init.py
python run_tests.py -stack vagrant_remote -xunit -config config.vagrant -test tests
exit
