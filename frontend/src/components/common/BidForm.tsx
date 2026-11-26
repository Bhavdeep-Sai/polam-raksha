import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { AccessibleFormField } from "@/components/common/AccessibleFormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const bidSchema = z.object({
  bidPriceRupeesPerKg: z.coerce.number().positive(),
  requestedKg: z.coerce.number().positive(),
  minAcceptableKg: z.coerce.number().positive(),
}).refine((val) => val.minAcceptableKg <= val.requestedKg, {
  path: ["minAcceptableKg"],
  message: "Minimum acceptable quantity cannot exceed requested quantity",
});

export type BidFormValues = z.infer<typeof bidSchema>;

interface BidFormProps {
  minBidPaisePerKg: number;
  disabled?: boolean;
  onSubmitBid: (payload: {
    bidPricePaisePerKg: number;
    requestedQuantityGrams: number;
    minAcceptableGrams: number;
  }) => void;
}

export function BidForm({ minBidPaisePerKg, disabled = false, onSubmitBid }: BidFormProps) {
  const { t } = useTranslation();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<BidFormValues>({
    resolver: zodResolver(bidSchema),
    defaultValues: {
      bidPriceRupeesPerKg: Math.ceil(minBidPaisePerKg / 100),
      requestedKg: 50,
      minAcceptableKg: 25,
    },
  });

  const handleFormSubmit = (values: BidFormValues) => {
    onSubmitBid({
      bidPricePaisePerKg: Math.round(values.bidPriceRupeesPerKg * 100),
      requestedQuantityGrams: Math.round(values.requestedKg * 1000),
      minAcceptableGrams: Math.round(values.minAcceptableKg * 1000),
    });
  };

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4">
      <AccessibleFormField
        id="bid-price"
        label={t("auction.bidPriceLabel")}
        error={errors.bidPriceRupeesPerKg?.message}
        required
      >
        <Input
          id="bid-price"
          type="number"
          step="0.5"
          min="1"
          disabled={disabled}
          {...register("bidPriceRupeesPerKg")}
        />
      </AccessibleFormField>

      <div className="grid gap-4 sm:grid-cols-2">
        <AccessibleFormField
          id="bid-requested-kg"
          label={t("auction.requestedQtyLabel")}
          error={errors.requestedKg?.message}
          required
        >
          <Input
            id="bid-requested-kg"
            type="number"
            step="1"
            min="1"
            disabled={disabled}
            {...register("requestedKg")}
          />
        </AccessibleFormField>

        <AccessibleFormField
          id="bid-min-kg"
          label={t("auction.minAcceptableQtyLabel")}
          error={errors.minAcceptableKg?.message}
          required
        >
          <Input
            id="bid-min-kg"
            type="number"
            step="1"
            min="1"
            disabled={disabled}
            {...register("minAcceptableKg")}
          />
        </AccessibleFormField>
      </div>

      <Button type="submit" disabled={disabled || isSubmitting} className="w-full sm:w-auto">
        {t("auction.submitBid")}
      </Button>
    </form>
  );
}

