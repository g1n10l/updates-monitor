#!/bin/sh
# The completion message follows the process locale; English is the fallback.
updates_monitor_install_message() {
    locale_name=${LC_ALL:-${LC_MESSAGES:-${LANG:-C}}}
    case "$locale_name" in
        pl|pl_*|pl-*) message='Domyślnie interwał sprawdzania aktualizacji jest ustawiony na 1 dzień.' ;;
        de|de_*|de-*) message='Das Standardintervall für die Suche nach Aktualisierungen beträgt 1 Tag.' ;;
        fr|fr_*|fr-*) message='Par défaut, la recherche de mises à jour est effectuée tous les jours.' ;;
        es|es_*|es-*) message='De forma predeterminada, las actualizaciones se comprueban cada día.' ;;
        *) message='By default, updates are checked once per day.' ;;
    esac
    if [ -t 1 ]; then
        printf '\033[1m%s\033[0m\n' "$message"
    else
        printf '%s\n' "$message"
    fi
}
