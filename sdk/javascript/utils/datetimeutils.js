

class DateTimeUtils {
    constructor(utc_offset) {
        this.__utc_offset = utc_offset
    }
    
    // adjust the given timestamp to the local timezone
    timezone(timestamp) {
       return parseInt(timestamp+this.__utc_offset*3600)
    }

    // adjust the given timestamp to utc
    utc(timestamp) {
       return parseInt(timestamp-this.__utc_offset*3600)
    }
    
    // return the current timestamp, in the local timezone
    now() {
        return this.timezone(parseInt(Date.now()/1000), this.__utc_offset)
    }
    
    // format the provided timestamp for printing
    format_timestamp(timestamp=this.now()) {
        var date = new Date(this.utc(timestamp) * 1000)
        var day = date.getDate() < 10 ? "0"+date.getDate() : date.getDate()
        var month = (date.getMonth()+1) < 10 ? "0"+(date.getMonth()+1) : date.getMonth()+1
        var year = date.getFullYear()
        var hour = date.getHours() < 10 ? "0"+date.getHours() : date.getHours()
        var minute = date.getMinutes() < 10 ? "0"+date.getMinutes() : date.getMinutes()
        var second = date.getSeconds() < 10 ? "0"+date.getSeconds() : date.getSeconds()
        return day+"/"+month+"/"+year+" "+hour+":"+minute+":"+second
    }

    // return the difference between two timestamps in a human readable format
    timestamp_difference(date1, date2) {
        if (date1 == "" || date2 == "") return "N.A"
        // TODO: localization
        var seconds = Math.floor(Math.abs(date1-date2))
        var interval = Math.floor(seconds / 31536000)
        if (interval > 1) return String(parseInt(interval)) + " years ago"
        interval = Math.floor(seconds / 2592000)
        if (interval > 1) return String(parseInt(interval)) + " months ago"
        interval = Math.floor(seconds / 86400)
        if (interval > 1) return String(parseInt(interval)) + " days ago"
        interval = Math.floor(seconds / 3600)
        if (interval > 1) return String(parseInt(interval)) + " hours ago"
        interval = Math.floor(seconds / 60)
        if (interval > 1) return String(parseInt(interval)) + " minutes ago"
        return String(parseInt(Math.floor(seconds))) + " seconds ago"
    }
}
