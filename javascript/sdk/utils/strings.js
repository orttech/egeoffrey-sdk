// capitalize the first letter
function capitalizeFirst(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
}

String.prototype.replaceAll = function(search, replacement) {
var target = this;
return target.replace(new RegExp(search, 'g'), replacement);
};

function get_exception(e) {
    return e.stack
}

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