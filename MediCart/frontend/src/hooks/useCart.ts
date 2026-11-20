import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import { cartApi } from "@/services/api";
import { toApiError } from "@/services/http";
import type { Cart } from "@/types";

export const CART_KEY = ["cart"];

export function useCart() {
  const { isAuthenticated, user } = useAuth();
  const queryClient = useQueryClient();
  const toast = useToast();
  const enabled = isAuthenticated && user?.role === "customer";

  const query = useQuery({
    queryKey: CART_KEY,
    queryFn: cartApi.get,
    enabled,
    staleTime: 30_000,
  });

  const apply = (cart: Cart) => queryClient.setQueryData(CART_KEY, cart);
  const fail = (error: unknown, fallback: string) => {
    const apiError = toApiError(error);
    toast.error(fallback, apiError.message);
  };

  const add = useMutation({
    mutationFn: ({ productId, quantity }: { productId: number; quantity?: number }) =>
      cartApi.add(productId, quantity ?? 1),
    onSuccess: (cart) => {
      apply(cart);
      toast.success("Added to cart");
    },
    onError: (error) => fail(error, "Could not add to cart"),
  });

  const update = useMutation({
    mutationFn: ({ itemId, quantity }: { itemId: number; quantity: number }) => cartApi.update(itemId, quantity),
    onSuccess: apply,
    onError: (error) => fail(error, "Could not update quantity"),
  });

  const remove = useMutation({
    mutationFn: (itemId: number) => cartApi.remove(itemId),
    onSuccess: (cart) => {
      apply(cart);
      toast.info("Removed from cart");
    },
    onError: (error) => fail(error, "Could not remove item"),
  });

  const clear = useMutation({
    mutationFn: cartApi.clear,
    onSuccess: apply,
    onError: (error) => fail(error, "Could not clear cart"),
  });

  return {
    cart: query.data,
    isLoading: query.isLoading && enabled,
    itemCount: query.data?.item_count ?? 0,
    add,
    update,
    remove,
    clear,
    refetch: query.refetch,
  };
}
