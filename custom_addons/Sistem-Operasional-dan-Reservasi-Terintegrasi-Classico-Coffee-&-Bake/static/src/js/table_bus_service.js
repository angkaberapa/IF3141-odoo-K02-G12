/** @odoo-module **/

/*
kata gemini, kalau mau "real-time" (as written di milestone 4), perlu pakai bus, jadi di-sini behaviournya dia bakal nge-subscribe gitu ke table. terus kalau misal ada changes bakal forced refresh + dapet notif gitu. jujur belum nyoba di 2 akun berbeda. kalau di 2 akun yang sama dia ke-fire sih notif + auto-refreshnya
*/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const tableBusService = {
    dependencies: ["action", "bus_service", "notification"],

    start(env, { action, bus_service, notification }) {
        bus_service.addChannel("classico_table_status");
        bus_service.addEventListener("notification", async ({ detail: notifications }) => {
            for (const notificationData of notifications) {
                const { type, payload } = notificationData;
                if (type !== "classico_table_status_changed") {
                    continue;
                }

                env.bus.trigger("classico-table-status-changed", payload);
                const refreshed = await refreshTableView(action);
                notification.add(refreshed
                    ? _t("Status meja diperbarui otomatis.")
                    : _t("Status meja diperbarui. Buka dashboard meja untuk melihat data terbaru."), {
                    title: _t("Classico Coffee & Bake"),
                    type: "info",
                    sticky: false,
                });
            }
        });
    },
};

async function refreshTableView(action) {
    const current = action.currentController;
    const controller = current?.controller || current;
    const resModel = current?.action?.res_model || current?.props?.resModel || controller?.props?.resModel;

    if (resModel !== "classico.table") {
        return false;
    }

    if (controller?.model?.root?.load) {
        await controller.model.root.load();
        controller.render(true);
        return true;
    }

    if (current?.action) {
        await action.doAction(current.action, { clearBreadcrumbs: false });
        return true;
    }

    return false;
}

registry.category("services").add("classico_table_bus_service", tableBusService);
