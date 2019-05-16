// capitalize the first letter
function capitalizeFirst(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
}

// replace all instances of search in replacement
String.prototype.replaceAll = function(search, replacement) {
var target = this;
return target.replace(new RegExp(search, 'g'), replacement);
};

// return stack trace exception
function get_exception(e) {
    return e.stack
}

// remove one element from an array
Array.prototype.remove = function() {
    var what, a = arguments, L = a.length, ax;
    while (L && this.length) {
        what = a[--L];
        while ((ax = this.indexOf(what)) !== -1) {
            this.splice(ax, 1);
        }
    }
    return this;
};

// truncate a long string 
function truncate(string, max_len=50) {
    if (string == null) string = ""
    return string.length > max_len ? (string.substring(0, max_len) + '...') : string
}

// javascript implementation of topic_matches_sub
function topic_matches_sub(pattern, topic) {
        // replace + with a different placeholder which doesn't need to be escaped
        pattern = pattern.replaceAll('\\+', '!!!')
        // escape the pattern
        pattern = pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') 
        // replace mqtt operators + and # with regexp equivalent
        pattern = pattern.replaceAll('#', '.*$')
        pattern = pattern.replaceAll('!!!', '[^\/]+')
        if (String(topic).search(pattern) == 0) return true
        return false
}

// format a log line for printing
function format_log_line(severity, module, text) {
    var now = Date()
    return "["+now.toLocaleString()+"]["+module+"] "+severity.toUpperCase()+ ": "+truncate(text, 2000)
}