git diff --name-only HEAD | while read file; do
    if [ -f "$file" ]; then
        # Ottieni il timestamp del file locale
        local_time=$(stat -c %Y "$file" 2>/dev/null || stat -f %m "$file" 2>/dev/null)
        
        # Ottieni il timestamp dell'ultimo commit per questo file
        commit_time=$(git log -1 --format=%ct -- "$file")
        
        # Se il file locale è più vecchio, ripristinalo
        if [ "$local_time" -lt "$commit_time" ]; then
            echo "Ripristino $file (locale più vecchio)"
            git restore "$file"
        else
            echo "Mantengo $file (locale più recente)"
        fi
    fi
done
