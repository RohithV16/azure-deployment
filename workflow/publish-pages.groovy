import com.day.cq.replication.Replicator
import com.day.cq.replication.ReplicationActionType
import com.day.cq.replication.ReplicationOptions
import com.day.cq.search.QueryBuilder
import com.day.cq.search.PredicateGroup
import com.day.cq.search.result.Hit

import javax.jcr.Node
import javax.jcr.Session

//==================================================
// Configuration
//==================================================

boolean DRY_RUN = true
boolean REQUIRE_CONFIRMATION = true
boolean CONFIRMED = false
int BATCH_SIZE = 50
int MAX_RETRIES = 2
long RETRY_DELAY_MS = 500L

List<String> ROOT_PATHS = [
        "/content/mandg/adviser",
        "/content/mandg/customer"
]

//==================================================

def session = resourceResolver.adaptTo(Session)
def queryBuilder = getService(QueryBuilder)
def replicator = getService(Replicator)

if (!session || !queryBuilder || !replicator) {

    println "ERROR: Could not initialize required services."
    println "  session     : ${session ? 'OK' : 'MISSING'}"
    println "  queryBuilder: ${queryBuilder ? 'OK' : 'MISSING'}"
    println "  replicator  : ${replicator ? 'OK' : 'MISSING'}"
    return
}

if (BATCH_SIZE <= 0) {
    println "ERROR: BATCH_SIZE must be greater than 0."
    return
}

if (!ROOT_PATHS || ROOT_PATHS.isEmpty()) {
    println "ERROR: ROOT_PATHS is empty."
    return
}

List<String> missingRoots = ROOT_PATHS.findAll { !session.nodeExists(it) }
if (!missingRoots.isEmpty()) {

    println "ERROR: Some root paths do not exist:"
    missingRoots.each { println "  ${it}" }
    return
}

if (REQUIRE_CONFIRMATION && !DRY_RUN && !CONFIRMED) {
    println "ERROR: Publishing is blocked. Set CONFIRMED = true to run non-dry-run mode."
    return
}

Set<String> pagePaths = new TreeSet<>()
Set<String> templatePaths = new TreeSet<>()
Set<String> templateNodePaths = new LinkedHashSet<>()

List<String> failedPages = []
List<String> failedTemplateNodes = []

//==================================================
// Replication helpers
//==================================================

def replicateWithRetry
replicateWithRetry = { Object target ->

    ReplicationOptions replicationOptions = new ReplicationOptions()

    int attempt = 0

    while (attempt <= MAX_RETRIES) {

        try {

            if (target instanceof String[]) {
                replicator.replicate(session, ReplicationActionType.ACTIVATE, target as String[], replicationOptions)
            } else {
                replicator.replicate(session, ReplicationActionType.ACTIVATE, target as String)
            }
            return true

        } catch (Exception ex) {

            if (attempt == MAX_RETRIES) {
                println "Replication failed after ${MAX_RETRIES + 1} attempts: ${ex.message}"
                return false
            }

            int nextAttempt = attempt + 2
            println "Replication attempt ${attempt + 1} failed. Retrying (${nextAttempt}/${MAX_RETRIES + 1})..."
            println "  ${ex.message}"
            Thread.sleep(RETRY_DELAY_MS)
            attempt++
        }
    }

    return false
}

def publishBatches
publishBatches = { Collection<String> paths, String label, String failureLabel, List<String> failures ->

    println ""
    println "=================================================="
    println "Publishing ${label}"
    println "=================================================="

    if (paths.isEmpty()) {
        println "No ${label.toLowerCase()} to publish."
        return
    }

    paths.collate(BATCH_SIZE).eachWithIndex { batch, index ->

        println "Batch ${index + 1} (${batch.size()} ${label.toLowerCase()})"

        if (!replicateWithRetry(batch as String[])) {

            println "Batch failed. Falling back to individual publishing."

            batch.each { String path ->

                if (!replicateWithRetry(path)) {
                    failures.add(path)
                    println "FAILED ${failureLabel}: ${path}"
                }
            }
        }
    }
}

//==================================================
// Collect template immediate child nodes only
//==================================================

def collectTemplateImmediateChildren

collectTemplateImmediateChildren = { Node templateNode ->

    templateNode.nodes.each { Node child ->
        templateNodePaths.add(child.path)
    }
}

//==================================================
// Scan Pages
//==================================================

println "=================================================="
println "Scanning Pages..."
println "=================================================="

ROOT_PATHS.each { rootPath ->

    println "Scanning: ${rootPath}"

    Map<String, String> predicates = [
            "path"    : rootPath,
            "type"    : "cq:PageContent",
            "p.limit" : "-1"
    ]

    def query = queryBuilder.createQuery(
            PredicateGroup.create(predicates),
            session
    )

    query.result.hits.each { Hit hit ->

        String contentPath = hit.path
        String pagePath = contentPath.replace("/jcr:content", "")

        pagePaths.add(pagePath)

        Node content = session.getNode(contentPath)

        if (content.hasProperty("cq:template")) {

            String template = content.getProperty("cq:template").string

            if (!template.startsWith("/apps/")) {
                templatePaths.add(template)
            }
        }
    }
}

//==================================================
// Collect Template Nodes
//==================================================

println ""
println "Collecting template nodes..."

templatePaths.each { template ->

    if (session.nodeExists(template)) {
        collectTemplateImmediateChildren(session.getNode(template))
    } else {
        println "Template not found: ${template}"
    }
}

//==================================================
// Summary
//==================================================

println ""
println "=================================================="
println "Summary"
println "=================================================="

println "Pages            : ${pagePaths.size()}"
println "Templates        : ${templatePaths.size()}"
println "Template Nodes   : ${templateNodePaths.size()}"
println "Batch Size       : ${BATCH_SIZE}"
println "Mode             : ${DRY_RUN ? 'DRY RUN' : 'PUBLISH'}"

if (DRY_RUN) {

    println ""
    println "Templates:"
    templatePaths.each {
        println it
    }

    println ""
    println "Dry run completed."
    return
}

publishBatches(pagePaths, "Pages", "PAGE", failedPages)
publishBatches(templateNodePaths, "Template Nodes", "TEMPLATE NODE", failedTemplateNodes)

//==================================================
// Final Summary
//==================================================

println ""
println "=================================================="
println "Completed"
println "=================================================="

println "Pages Published           : ${pagePaths.size() - failedPages.size()}"
println "Pages Failed              : ${failedPages.size()}"

println "Template Nodes Published  : ${templateNodePaths.size() - failedTemplateNodes.size()}"
println "Template Nodes Failed     : ${failedTemplateNodes.size()}"

if (!failedPages.isEmpty()) {

    println ""
    println "Failed Pages"

    failedPages.each {
        println it
    }
}

if (!failedTemplateNodes.isEmpty()) {

    println ""
    println "Failed Template Nodes"

    failedTemplateNodes.each {
        println it
    }
}