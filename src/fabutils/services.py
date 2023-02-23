from fabric import Connection


def enable(c: Connection, service: str):
    c.run(f"update-rc.d {service} defaults")
    c.run(f"service {service} start")


def disable(c: Connection, service: str):
    c.run(f"update-rc.d {service} disable")
    c.run(f"service {service} stop")
