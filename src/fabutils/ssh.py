from fabric.connection import Connection


def disable_root_login_with_password(c: Connection):
    c.run("sed -i 's:RootLogin yes:RootLogin without-password:' /etc/ssh/sshd_config", echo=True)
    c.run("service ssh restart", echo=True)
