import javax.jcr.Node
import javax.jcr.Session

Session session = resourceResolver.adaptTo(Session)

// ============================================================================
// CONFIGURATION
// ============================================================================
String workflowModel = "/var/workflow/models/content-approval-workflow-updated-global"

// ============================================================================

Node root = session.getNode("/var/workflow/instances")

int matched = 0

def payloads = [] as List<String>
def statusCounts = [:].withDefault { 0 }

def traverse

traverse = { Node node ->

    if (node.isNodeType("cq:Workflow")) {

        if (node.hasProperty("modelId") &&
                node.getProperty("modelId").string == workflowModel) {

            String status = node.hasProperty("status")
                    ? node.getProperty("status").string
                    : "RUNNING"

            // Count every workflow regardless of filter
            statusCounts[status]++

            matched++

            String payload = "N/A"

            if (node.hasNode("data/payload")) {
                Node payloadNode = node.getNode("data/payload")
                if (payloadNode.hasProperty("path")) {
                    payload = payloadNode.getProperty("path").string
                    payloads << payload
                }
            }

            println "=================================================================="
            println "Workflow : ${node.path}"
            println "Status   : ${status}"
            println "Payload  : ${payload}"
        }
    }

    // Prevent ConcurrentModificationException
    def children = []
    node.nodes.each { children << it }

    children.each { child ->
        traverse(child)
    }
}

traverse(root)

println ""
println "==================== PAYLOADS ===================="

payloads.unique().sort().eachWithIndex { payload, index ->
    println "${index + 1}. ${payload}"
}

println ""
println "==================== SUMMARY ====================="
println "Workflow Model : ${workflowModel}"
println "Matched        : ${matched}"
println "Unique Payloads: ${payloads.unique().size()}"

println ""
println "Workflow Status Counts"
println "----------------------"

statusCounts.keySet().sort().each { status ->
    println String.format("%-12s : %d", status, statusCounts[status])
}

println "----------------------"
println String.format("%-12s : %d", "TOTAL", statusCounts.values().sum() ?: 0)