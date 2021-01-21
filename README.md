Downstream SAP fork for untested features and secrete stuff.
Please, use the upstream repo for new code [https://github.com/jfilak/sapcli](https://github.com/jfilak/sapcli).

## Update process

1. git clone https://github.com/jfilak/sapcli
2. cd sapcli
3. git remote add sap\_fork https://github.wdf.sap.corp/factory/sapcli
4. git checkout -b sap\_fork\_master sap\_fork/master
7. git rebase origin/master
8. git push sap\_fork HEAD:master -f
