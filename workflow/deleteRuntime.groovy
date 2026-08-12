import javax.jcr.Session

def session = resourceResolver.adaptTo(Session)

def nodePath = "/var/workflow/instances/server1056/2026-07-07"

if (session.nodeExists(nodePath)) {
    session.getNode(nodePath).remove()
    session.save()
    println "Deleted node: ${nodePath}"
} else {
    println "Node does not exist: ${nodePath}"
}