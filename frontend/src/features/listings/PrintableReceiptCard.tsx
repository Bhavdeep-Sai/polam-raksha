import { Printer } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { CurrencyDisplay } from "@/components/common/CurrencyDisplay";
import { ErrorState } from "@/components/common/ErrorState";
import { QuantityDisplay } from "@/components/common/QuantityDisplay";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { formatIstDateTime } from "@/lib/format";
import { apiClient, ApiError, type ListingReceiptResponse } from "@/services/api";

export function PrintableReceiptCard({ listingId }: { listingId: string }) {
  const { t, i18n } = useTranslation();
  const [receipt, setReceipt] = useState<ListingReceiptResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadReceipt = async () => {
    setErrorMsg(null);
    try {
      const data = await apiClient.getListingReceipt(listingId);
      setReceipt(data);
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : t("common.errorTitle"));
    }
  };

  return (
    <div className="space-y-2">
      <Button variant="outline" size="sm" onClick={() => void loadReceipt()}>
        <Printer className="h-4 w-4" aria-hidden="true" />
        Printable Receipt
      </Button>

      {errorMsg ? <ErrorState message={errorMsg} /> : null}

      {receipt ? (
        <Card className="space-y-1.5 border-2 border-dashed border-brand-primary bg-white text-xs">
          <p className="font-bold text-brand-primary">PolamRaksha Receipt</p>
          <p>
            <strong>Farmer:</strong> {receipt.farmer_name} ({receipt.farmer_id.slice(0, 8)})
          </p>
          <p>
            <strong>Listing ID:</strong> {receipt.listing_id}
          </p>
          <p>
            <strong>Crop:</strong> {receipt.crop_name_te} / {receipt.crop_name_en}
          </p>
          <p>
            <strong>Quantity:</strong> <QuantityDisplay grams={receipt.total_quantity_grams} />
          </p>
          <p>
            <strong>Minimum Price:</strong>{" "}
            <CurrencyDisplay paise={receipt.floor_price_paise_per_kg} suffix="/ kg" />
          </p>
          <p>
            <strong>Collection Deadline:</strong>{" "}
            {formatIstDateTime(receipt.collection_deadline_at, i18n.language)}
          </p>
          <p>
            <strong>Centre:</strong> {receipt.operator_or_centre_info}
          </p>
        </Card>
      ) : null}
    </div>
  );
}

