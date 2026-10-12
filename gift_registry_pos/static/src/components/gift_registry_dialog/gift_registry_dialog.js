import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { _t } from "@web/core/l10n/translation";

export class GiftRegistryDialog extends Component {
    static template = "gift_registry_pos.GiftRegistryDialog";
    static components = { Dialog };
    static props = { getPayload: Function, close: Function };

    setup() {
        this.pos = usePos();
        this.state = useState({
            query: "", results: [], selected: null, searching: false, searched: false,
        });
    }

    get isOffline() {
        return this.pos.data.network.offline;
    }

    async search() {
        const query = this.state.query.trim();
        if (query.length < 3) {
            return;
        }
        this.state.searching = true;
        try {
            let found = false;
            if (!this.isOffline) {
                // Busca en todo Odoo y conecta el resultado con los modelos locales
                found = await this.pos.data.callRelated(
                    "gift.registry", "search_for_pos", [query, this.pos.config.id],
                    {}, false, true
                );
            }
            // Con conexión manda el servidor: solo él conoce el DNI y ya aplica la privacidad.
            // Sin conexión se filtra lo cargado al abrir la caja (código o nombre).
            this.state.results = found
                ? found["gift.registry"] || []
                : this.searchLocal(query);
            this.state.selected = null;
            this.state.searched = true;
        } finally {
            this.state.searching = false;
        }
    }

    searchLocal(query) {
        const q = query.toLowerCase();
        return this.pos.models["gift.registry"].getAll().filter((registry) => {
            const byCode = registry.name.toLowerCase() === q;
            const byName =
                registry.privacy === "public" &&
                `${registry.partner_name} ${registry.title}`.toLowerCase().includes(q);
            return byCode || byName;
        });
    }

    qtyInCurrentOrder(registryLine) {
        const order = this.pos.getOrder();
        return (order?.lines || [])
            .filter((l) => l.gift_registry_line_id?.id === registryLine.id)
            .reduce((total, l) => total + l.qty, 0);
    }

    pendingFor(registryLine) {
        return registryLine.qty_pending - this.qtyInCurrentOrder(registryLine);
    }

    // --- Presentación ---------------------------------------------------------
    /** "sábado, 17 de octubre de 2026" en el idioma del usuario. */
    eventDateLabel(registry) {
        const date = registry.event_date;
        if (!date?.isValid) {
            return date ? String(date) : "";
        }
        return date.toLocaleString({
            weekday: "long", day: "numeric", month: "long", year: "numeric",
        });
    }

    /** 3 -> "3"; 2.5 -> "2.5" (las cantidades casi siempre son enteras). */
    formatQty(qty) {
        return Number.isInteger(qty) ? String(qty) : String(parseFloat(qty.toFixed(2)));
    }

    /**
     * Avance de la lista. Igual que el aviso diario: se cuenta por producto y sin
     * pasar de lo deseado, así un regalo de más no compensa a otro que falta.
     */
    progressOf(registry) {
        let wanted = 0;
        let covered = 0;
        for (const line of registry.line_ids) {
            wanted += line.qty_wanted;
            covered += Math.max(Math.min(line.qty_gifted, line.qty_wanted), 0);
        }
        const complete = wanted > 0 && covered >= wanted;
        return {
            wanted, covered, complete,
            percent: complete ? 100 : wanted ? Math.floor((covered / wanted) * 100) : 0,
            // Un segmento por regalo solo si son pocos y enteros; si no, barra continua
            segments: Number.isInteger(wanted) && wanted > 1 && wanted <= 12 ? wanted : 0,
        };
    }

    /** "pending": se puede agregar · "out": falta pero no hay stock · "done": nada pendiente. */
    lineState(registryLine) {
        if (this.pendingFor(registryLine) <= 0) {
            return "done";
        }
        return registryLine.product_id && registryLine.qty_available > 0 ? "pending" : "out";
    }

    /** Pendientes primero, luego agotados y al final los ya cubiertos. */
    sortedLines(registry) {
        const order = { pending: 0, out: 1, done: 2 };
        return [...registry.line_ids].sort(
            (a, b) => order[this.lineState(a)] - order[this.lineState(b)]
        );
    }

    productName(registryLine) {
        return registryLine.product_id?.display_name || _t("Producto no disponible en esta caja");
    }

    imageUrl(registryLine) {
        return registryLine.product_id?.getImageUrl?.() || "";
    }

    async pick(registryLine) {
        if (!this.isOffline) {
            // Revalida justo antes de agregar: otra caja pudo venderlo
            await this.pos.data.callRelated(
                "gift.registry.line", "get_status_for_pos",
                [[registryLine.id], this.pos.config.id]
            );
        }
        if (this.pendingFor(registryLine) <= 0) {
            this.pos.notification.add(_t("Este regalo ya fue cubierto."), { type: "warning" });
            return;
        }
        this.props.getPayload(registryLine);
        this.props.close();
    }
}
