import { patch } from "@web/core/utils/patch";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { GiftRegistryDialog } from "../components/gift_registry_dialog/gift_registry_dialog";

patch(ControlButtons.prototype, {
    async onClickGiftRegistry() {
        const picked = await makeAwaitable(this.dialog, GiftRegistryDialog, {});
        if (!picked) {
            return;
        }
        const { registryLine, message } = picked;
        const product = registryLine.product_id;
        await this.pos.addLineToCurrentOrder(
            {
                product_tmpl_id: product.product_tmpl_id,
                product_id: product,
                qty: 1,
                gift_registry_line_id: registryLine,
                gift_message: message || false,
            },
            { merge: false } // no fusionar con una venta normal del mismo producto
        );
    },
});

patch(PosOrderline.prototype, {
    canBeMergedWith(orderline) {
        if (this.gift_registry_line_id?.id !== orderline.gift_registry_line_id?.id) {
            return false;
        }
        return super.canBeMergedWith(...arguments);
    },
});
