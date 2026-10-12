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
        this.state = useState({ query: "", results: [], selected: null, searching: false });
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
            if (!this.isOffline) {
                // Busca en todo Odoo y conecta el resultado con los modelos locales
                await this.pos.data.callRelated(
                    "gift.registry", "search_for_pos", [query, this.pos.config.id],
                    {}, false, true
                );
            }
            this.state.results = this.searchLocal(query);
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
